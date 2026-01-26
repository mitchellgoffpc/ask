import asyncio
import glob
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, ClassVar

from ask.config import History
from ask.models import MODELS_BY_NAME, Model
from ask.ui.core import Component, Box, Text, Widget, Controller, TextBox, Axis, Colors, Styles, Theme
from ask.ui.dialogs import EDIT_TOOLS

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
    Mode.BASH: '! for bash mode',
    Mode.MEMORIZE: '# to memorize',
    Mode.PYTHON: '$ for python mode',
    Mode.TEXT: '! for bash mode · $ for python · / for commands'}
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

def CommandName(name: str, active: bool) -> Text:
    return Text(Styles.bold(Colors.hex(name, Theme.BLUE if active else Theme.GRAY)))

def CommandDesc(desc: str, active: bool) -> Text:
    return Text(Colors.hex(desc, Theme.BLUE if active else Theme.GRAY))

def CommandsList(commands: dict[str, str], selected_idx: int) -> Box:
    return Box(flex=Axis.HORIZONTAL)[
        Box(margin={'left': 2})[(CommandName(cmd, idx == selected_idx) for idx, cmd in enumerate(commands.keys()))],
        Box(margin={'left': 3})[(CommandDesc(desc, idx == selected_idx) for idx, desc in enumerate(commands.values()))]
    ]


@dataclass
class PromptTextBox(Widget):
    __controller__: ClassVar = lambda _: PromptTextBoxController
    model: Model
    approved_tools: set[str]
    handle_submit: Callable[[str], bool]
    handle_exit: Callable[[], None]


class PromptTextBoxController(Controller):
    state = ['text', 'mode', 'show_exit_prompt', 'selected_idx', 'autocomplete_matches']
    text = ''
    mode = Mode.TEXT
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
                prefix = os.path.expanduser(prefix)
            matches = glob.glob(prefix + '*')
            matches = [os.path.basename(m) if '/' not in prefix else m for m in matches]
            return sorted(matches)[:10]
        except Exception:
            return []

    def get_shortcuts_text(self) -> str:
        if self.mode == Mode.TEXT and EDIT_TOOLS & self.props.approved_tools:
            return Colors.hex('⏵⏵ accept edits on ', Theme.PURPLE) + Colors.hex('(shift+tab to disable)', Theme.DARK_PURPLE)
        return Colors.hex(SHORTCUTS[self.mode], COLORS.get(self.mode, Theme.GRAY))

    def handle_input(self, ch: str) -> None:
        if ch == '\x03':  # Ctrl+C
            self.text = ''
            asyncio.create_task(self.confirm_exit())

    def handle_textbox_input(self, ch: str, cursor_pos: int) -> bool:
        if cursor_pos == 0 and ch in ('\x7f', '\x1b\x7f'):
            self.mode = Mode.TEXT
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

    def contents(self) -> list[Component | None]:
        matching_commands = self.get_matching_commands()
        matching_models = self.get_matching_models()
        autocomplete_matches = self.autocomplete_matches

        return [
            Box(flex=Axis.HORIZONTAL, width=1.0, margin={'top': 1}, border=('top', 'bottom'), border_color=Colors.HEX(COLORS.get(self.mode, Theme.DARK_GRAY)))[
                Text(Colors.hex(PREFIXES.get(self.mode, '>'), COLORS.get(self.mode, Theme.GRAY)), margin={'left': 1, 'right': 1}, width=3),
                TextBox(
                    width=1.0,
                    text=self.text,
                    history=History['queries'],
                    placeholder=PLACEHOLDERS[self.mode],
                    handle_input=self.handle_textbox_input,
                    handle_page=self.handle_textbox_page,
                    handle_change=self.handle_textbox_change,
                    handle_submit=self.handle_textbox_submit)
            ],
            Text(Colors.hex('Press Ctrl+C again to exit', Theme.GRAY), margin={'left': 2})
                if self.show_exit_prompt else
            CommandsList({match: '' for match in autocomplete_matches}, self.selected_idx)
                if autocomplete_matches else
            CommandsList({model: MODELS_BY_NAME[model].api.display_name for model in matching_models}, self.selected_idx)
                if matching_models else
            CommandsList(matching_commands, self.selected_idx)
                if matching_commands else
            Box(flex=Axis.HORIZONTAL)[
                Text(self.get_shortcuts_text(), width=1.0, margin={'left': 2}),
                Text(Colors.hex(self.props.model.api.display_name, Theme.WHITE)),
                Text(Colors.hex(self.props.model.name, Theme.GRAY), margin={'left': 2, 'right': 2})
            ]
        ]
