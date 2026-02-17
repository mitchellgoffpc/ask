import asyncio
import glob
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ask.config import History
from ask.models import MODELS_BY_NAME, Model
from ask.ui.core import UI, Axis, Colors, Styles
from ask.ui.dialogs import EDIT_TOOLS
from ask.ui.theme import Theme


class Mode(Enum):
    TEXT = 'text'
    BASH = 'bash'
    MEMORIZE = 'memorize'
    PYTHON = 'python'

COLORS = {
    Mode.BASH: Theme.PINK,
    Mode.MEMORIZE: Theme.BLUE,
    Mode.PYTHON: Theme.GREEN}
PREFIXES = {
    Mode.BASH: '!',
    Mode.MEMORIZE: '#',
    Mode.PYTHON: '$'}
SHORTCUTS = {
    '!': 'Run bash command',
    '$': 'Run python code',
    '#': 'Add to memory',
    '/': 'Run slash command'}

PLACEHOLDERS = {
    Mode.BASH: "Run bash command. Try 'ls -la'",
    Mode.MEMORIZE: "Add to memory. Try 'Always use descriptive variable names'",
    Mode.PYTHON: "Run python code. Try 'print(2 + 2)'",
    Mode.TEXT: "Try 'how do I log an error?'"}

COMMANDS = {
    '/clear': 'Clear conversation history and free up context',
    '/cost': 'Show the total cost and token usage for current session',
    '/init': 'Generate an AGENTS.md file with codebase documentation',
    '/model': 'Switch to a different model',
    '/exit': 'Exit the REPL',
    '/quit': 'Exit the REPL'}

def CommandName(name: str, active: bool) -> UI.Text:
    return UI.Text(Styles.bold(Colors.hex(name, Theme.BLUE) if active else Styles.bold(name)))

def CommandDesc(desc: str, active: bool) -> UI.Text:
    return UI.Text(Colors.hex(desc, Theme.BLUE) if active else desc)

def CommandsList(commands: dict[str, str], selected_idx: int) -> UI.Box:
    return UI.Box(flex=Axis.HORIZONTAL)[
        UI.Box(margin={'left': 2})[(CommandName(cmd, idx == selected_idx) for idx, cmd in enumerate(commands.keys()))],
        UI.Box(margin={'left': 3})[(CommandDesc(desc, idx == selected_idx) for idx, desc in enumerate(commands.values()))],
    ]


@dataclass
class PromptTextBox(UI.Widget):
    model: Model
    approved_tools: set[str]
    context_used: int
    handle_submit: Callable[[str], bool]
    handle_exit: Callable[[], None]

class PromptTextBoxController(UI.Controller[PromptTextBox]):
    state = ['text', 'mode', 'show_shortcuts', 'show_exit_prompt', 'selected_idx', 'autocomplete_matches']
    text = ''
    mode = Mode.TEXT
    show_shortcuts = False
    show_exit_prompt = False
    selected_idx = 0
    autocomplete_matches: list[str] = []

    async def confirm_exit(self) -> None:
        if self.show_exit_prompt:
            self.props.handle_exit()
        else:
            self.show_exit_prompt = True
            await asyncio.sleep(1)
            self.show_exit_prompt = False

    def get_current_word_prefix(self, text: str, cursor_pos: int) -> tuple[str, int]:
        if cursor_pos > len(text):
            cursor_pos = len(text)
        start = cursor_pos
        while start > 0 and text[start - 1] not in ' \t\n<>@|&;(){}[]"\'`':
            start -= 1
        return text[start:cursor_pos], start

    def get_matching_commands(self) -> dict[str, str]:
        return {cmd: desc for cmd, desc in COMMANDS.items() if self.text and cmd.startswith(self.text)}

    def get_matching_models(self) -> list[str]:
        if not self.text.startswith('/model '):
            return []
        model_prefix = self.text.removeprefix('/model ').lstrip()
        return [name for name in MODELS_BY_NAME if name.startswith(model_prefix)]

    def get_matching_paths(self, prefix: str) -> list[str]:
        if not prefix:
            return []
        try:
            if prefix.startswith('~'):
                prefix = str(Path(prefix).expanduser())
            matches = glob.glob(prefix + '*')  # noqa: PTH207
            matches = [Path(m).name if '/' not in prefix else m for m in matches]
            return sorted(matches)[:10]
        except Exception:
            return []

    def get_context_percent(self) -> str:
        max_context = self.props.model.context.max_length
        context_remaining = max(0, max_context - self.props.context_used)
        percent_remaining = int(100 * context_remaining / max_context)
        return f'{percent_remaining}% context remaining'

    def get_hint_text(self) -> str:
        if self.mode == Mode.TEXT and EDIT_TOOLS & self.props.approved_tools:
            return ' · ' + Colors.hex('⏵⏵ accept edits on ', Theme.PURPLE) + Colors.hex('(shift+tab to disable)', Theme.DARK_PURPLE)
        if not self.text:
            return ' · ' + '? for shortcuts'
        return ''

    def handle_input(self, ch: str) -> None:
        if ch == '\x03':  # Ctrl+C
            self.text = ''
            self.show_shortcuts = False
            asyncio.create_task(self.confirm_exit())
        elif ch in ('\x1b', '\x7f'):  # Escape, Backspace
            self.show_shortcuts = False

    def handle_textbox_input(self, ch: str, cursor_pos: int) -> bool:
        if cursor_pos == 0 and ch in ('\x7f', '\x1b\x7f'):
            self.mode = Mode.TEXT
        elif cursor_pos == 0 and ch == '?':
            self.show_shortcuts = not self.show_shortcuts
            return False
        elif cursor_pos == 0 and ch == '!':
            self.mode = Mode.BASH
            return False
        elif cursor_pos == 0 and ch == '#':
            self.mode = Mode.MEMORIZE
            return False
        elif cursor_pos == 0 and ch == '$':
            self.mode = Mode.PYTHON
            return False

        # Tab completion
        matching_commands = self.get_matching_commands()
        matching_models = self.get_matching_models()
        items = self.autocomplete_matches or list(matching_commands.keys()) or matching_models
        if ch == '\t':
            if matching_commands:
                self.text = list(matching_commands.keys())[self.selected_idx] + ' '
                return False
            elif matching_models:
                self.text = f"/model {matching_models[self.selected_idx]} "
                return False

            prefix, start_pos = self.get_current_word_prefix(self.text, cursor_pos)
            matching_paths = self.get_matching_paths(prefix)
            if len(matching_paths) == 1:
                completion = matching_paths[0] + ('/' if (Path(prefix).parent / matching_paths[0]).is_dir() else ' ')
                self.text = self.text[:start_pos] + completion + self.text[cursor_pos:]
                self.autocomplete_matches = []
            elif len(matching_paths) > 1:
                if self.autocomplete_matches:
                    self.selected_idx = (self.selected_idx + 1) % len(self.autocomplete_matches)
                else:
                    self.autocomplete_matches = matching_paths
                    self.selected_idx = 0
            return False
        elif ch == '\x1b[Z':  # Shift+Tab
            if self.autocomplete_matches:
                self.selected_idx = (self.selected_idx - 1) % len(self.autocomplete_matches)
            return False

        # Navigation for commands and autocomplete items
        if items and ch in ('\x1b[A', '\x10', '\x1b[B', '\x0e'):  # Up/Down arrows or Ctrl+P/N
            if ch in ('\x1b[A', '\x10'):
                self.selected_idx = (self.selected_idx - 1) % len(items)
            else:
                self.selected_idx = (self.selected_idx + 1) % len(items)
            return False
        return True

    def handle_textbox_page(self, _: int) -> None:
        self.mode = Mode.TEXT

    def handle_textbox_change(self, value: str) -> None:
        if value.startswith('!'):
            value = value.removeprefix('!')
            self.mode = Mode.BASH
        elif value.startswith('#'):
            value = value.removeprefix('#')
            self.mode = Mode.MEMORIZE
        elif value.startswith('$'):
            value = value.removeprefix('$')
            self.mode = Mode.PYTHON
        if value != self.text:
            self.selected_idx = 0
            self.autocomplete_matches = []
            if value:
                self.show_shortcuts = False
        self.text = value

    def handle_textbox_submit(self, value: str) -> bool:
        if not value:
            return False
        elif self.autocomplete_matches:
            selected_match = self.autocomplete_matches[self.selected_idx]
            _, start_pos = self.get_current_word_prefix(self.text, len(self.text))
            self.text = self.text[:start_pos] + selected_match + self.text[len(self.text):]
            self.autocomplete_matches = []
            return False
        elif matching_commands := self.get_matching_commands():
            value = f"{list(matching_commands.keys())[self.selected_idx]} "
        elif matching_models := self.get_matching_models():
            value = f"/model {matching_models[self.selected_idx]} "

        prefix = PREFIXES.get(self.mode, '')
        if self.props.handle_submit(f"{prefix}{value}"):
            self.text = ''
            self.mode = Mode.TEXT
            self.autocomplete_matches = []
            return True
        return False

    def contents(self) -> list[UI.Component | None]:
        matching_commands = self.get_matching_commands()
        matching_models = self.get_matching_models()

        return [
            UI.Box(flex=Axis.HORIZONTAL, width=1.0, margin={'top': 1}, padding={'bottom': 1, 'top': 1}, background_color=Theme.background())[
                UI.Text(PREFIXES.get(self.mode, '>'), margin={'left': 1, 'right': 1}, width=3),
                UI.TextBox(
                    width=1.0,
                    text=self.text,
                    placeholder=PLACEHOLDERS[self.mode],
                    highlight_color='#333333',
                    history=History['queries'],
                    handle_input=self.handle_textbox_input,
                    handle_page=self.handle_textbox_page,
                    handle_change=self.handle_textbox_change,
                    handle_submit=self.handle_textbox_submit),
            ],
            UI.Text('Press Ctrl+C again to exit', margin={'left': 2})
                if self.show_exit_prompt else
            CommandsList(dict.fromkeys(self.autocomplete_matches, ''), self.selected_idx)
                if self.autocomplete_matches else
            CommandsList({model: MODELS_BY_NAME[model].api.display_name for model in matching_models}, self.selected_idx)
                if matching_models else
            CommandsList(matching_commands, self.selected_idx)
                if matching_commands else
            CommandsList(SHORTCUTS, -1)
                if self.show_shortcuts else
            UI.Box(flex=Axis.HORIZONTAL)[
                UI.Text(self.get_context_percent() + self.get_hint_text(), width=1.0, margin={'left': 2}),
                UI.Text(self.props.model.api.display_name),
                UI.Text(self.props.model.name, margin={'left': 2, 'right': 2}),
            ],
        ]
