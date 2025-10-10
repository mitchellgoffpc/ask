import asyncio
import glob
import os
from enum import Enum
from pathlib import Path
from typing import Callable

from ask.models import MODELS_BY_NAME, Model
from ask.ui.core.components import Component, Box, Text
from ask.ui.core.styles import Borders, Colors, Flex, Styles, Theme
from ask.ui.core.textbox import TextBox
from ask.ui.dialogs import EditApproval

class Mode(Enum):
    TEXT = 'text'
    BASH = 'bash'
    MEMORIZE = 'memorize'

COLORS = {
    Mode.BASH: Theme.PINK,
    Mode.MEMORIZE: Theme.BLUE}
PREFIXES = {
    Mode.BASH: '!',
    Mode.MEMORIZE: '#'}
SHORTCUTS = {
    Mode.BASH: '! for bash mode',
    Mode.MEMORIZE: '# to memorize',
    Mode.TEXT: '! for bash mode · / for commands'}
PLACEHOLDERS = {
    Mode.BASH: "Run bash command. Try 'ls -la'",
    Mode.MEMORIZE: "Add to memory. Try 'Always use descriptive variable names'",
    Mode.TEXT: "Try 'how do I log an error?'"}

COMMANDS = {
    '/clear': 'Clear conversation history and free up context',
    '/cost': 'Show the total cost and token usage for current session',
    '/init': 'Generate an AGENTS.md file with codebase documentation',
    '/model': 'Switch to a different model',
    '/exit': 'Exit the REPL',
    '/quit': 'Exit the REPL',
    '/edit': 'Open file in editor'}

def CommandName(name: str, active: bool) -> Text:
    return Text(Styles.bold(Colors.hex(name, Theme.BLUE if active else Theme.GRAY)))

def CommandDesc(desc: str, active: bool) -> Text:
    return Text(Colors.hex(desc, Theme.BLUE if active else Theme.GRAY))

def CommandsList(commands: dict[str, str], selected_idx: int) -> Box:
    return Box(flex=Flex.HORIZONTAL)[
        Box(margin={'left': 2})[(CommandName(cmd, idx == selected_idx) for idx, cmd in enumerate(commands.keys()))],
        Box(margin={'left': 3})[(CommandDesc(desc, idx == selected_idx) for idx, desc in enumerate(commands.values()))]
    ]


class PromptTextBox(Box):
    initial_state = {'text': '', 'mode': Mode.TEXT, 'show_exit_prompt': False, 'selected_idx': 0, 'autocomplete_matches': []}

    def __init__(
        self,
        model: Model,
        history: list[str],
        autoapprovals: set[str],
        handle_submit: Callable[[str], bool],
        handle_exit: Callable[[], None]
    ) -> None:
        super().__init__(model=model, history=history, autoapprovals=autoapprovals, handle_submit=handle_submit, handle_exit=handle_exit)

    async def confirm_exit(self) -> None:
        if self.state['show_exit_prompt']:
            self.props['handle_exit']()
        else:
            self.state['show_exit_prompt'] = True
            await asyncio.sleep(1)
            self.state['show_exit_prompt'] = False

    def get_current_word_prefix(self, text: str, cursor_pos: int) -> tuple[str, int]:
        if cursor_pos > len(text):
            cursor_pos = len(text)
        start = cursor_pos
        while start > 0 and text[start - 1] not in ' \t\n<>@|&;(){}[]"\'`':
            start -= 1
        return text[start:cursor_pos], start

    def get_matching_commands(self) -> dict[str, str]:
        return {cmd: desc for cmd, desc in COMMANDS.items() if self.state['text'] and cmd.startswith(self.state['text'])}

    def get_matching_models(self) -> list[str]:
        if not self.state['text'].startswith('/model '):
            return []
        model_prefix = self.state['text'].removeprefix('/model ').lstrip()
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
        if self.state['mode'] == Mode.TEXT and EditApproval.autoapprovals & self.props['autoapprovals']:
            return Colors.hex('⏵⏵ accept edits on ', Theme.PURPLE) + Colors.hex('(shift+tab to disable)', Theme.DARK_PURPLE)
        return Colors.hex(SHORTCUTS[self.state['mode']], COLORS.get(self.state['mode'], Theme.GRAY))

    def handle_raw_input(self, ch: str) -> None:
        if ch == '\x03':  # Ctrl+C
            self.state['text'] = ''
            asyncio.create_task(self.confirm_exit())

    def handle_input(self, ch: str, cursor_pos: int) -> bool:
        if cursor_pos == 0 and ch in ('\x7f', '\x1b\x7f'):
            self.state['mode'] = Mode.TEXT
        elif cursor_pos == 0 and ch == '!':
            self.state['mode'] = Mode.BASH
            return False
        elif cursor_pos == 0 and ch == '#':
            self.state['mode'] = Mode.MEMORIZE
            return False

        # Tab completion
        matching_commands = self.get_matching_commands()
        matching_models = self.get_matching_models()
        items = self.state['autocomplete_matches'] or list(matching_commands.keys()) or matching_models
        if ch == '\t':
            if matching_commands:
                self.state['text'] = list(matching_commands.keys())[self.state['selected_idx']] + ' '
                return False
            elif matching_models:
                self.state['text'] = f"/model {matching_models[self.state['selected_idx']]} "
                return False

            prefix, start_pos = self.get_current_word_prefix(self.state['text'], cursor_pos)
            matching_paths = self.get_matching_paths(prefix)
            if len(matching_paths) == 1:
                completion = matching_paths[0] + ('/' if (Path(prefix).parent / matching_paths[0]).is_dir() else ' ')
                self.state['text'] = self.state['text'][:start_pos] + completion + self.state['text'][cursor_pos:]
                self.state['autocomplete_matches'] = []
            elif len(matching_paths) > 1:
                if self.state['autocomplete_matches']:
                    self.state['selected_idx'] = (self.state['selected_idx'] + 1) % len(self.state['autocomplete_matches'])
                else:
                    self.state['autocomplete_matches'] = matching_paths
                    self.state['selected_idx'] = 0
            return False
        elif ch == '\x1b[Z':  # Shift+Tab
            if self.state['autocomplete_matches']:
                self.state['selected_idx'] = (self.state['selected_idx'] - 1) % len(self.state['autocomplete_matches'])
            return False

        # Navigation for commands and autocomplete items
        if items and ch in ('\x1b[A', '\x10', '\x1b[B', '\x0e'):  # Up/Down arrows or Ctrl+P/N
            if ch in ('\x1b[A', '\x10'):
                self.state['selected_idx'] = (self.state['selected_idx'] - 1) % len(items)
            else:
                self.state['selected_idx'] = (self.state['selected_idx'] + 1) % len(items)
            return False
        return True

    def handle_page(self, _: int) -> None:
        self.state['mode'] = Mode.TEXT

    def handle_change(self, value: str) -> None:
        if value.startswith('!'):
            value = value.removeprefix('!')
            self.state['mode'] = Mode.BASH
        elif value.startswith('#'):
            value = value.removeprefix('#')
            self.state['mode'] = Mode.MEMORIZE
        if value != self.state['text']:
            self.state['selected_idx'] = 0
            self.state['autocomplete_matches'] = []
        self.state['text'] = value

    def handle_submit(self, value: str) -> bool:
        if self.state['autocomplete_matches']:
            selected_match = self.state['autocomplete_matches'][self.state['selected_idx']]
            _, start_pos = self.get_current_word_prefix(self.state['text'], len(self.state['text']))
            self.state['text'] = self.state['text'][:start_pos] + selected_match + self.state['text'][len(self.state['text']):]
            self.state['autocomplete_matches'] = []
            return False
        elif matching_commands := self.get_matching_commands():
            value = f"{list(matching_commands.keys())[self.state['selected_idx']]} "
        elif matching_models := self.get_matching_models():
            value = f"/model {matching_models[self.state['selected_idx']]} "

        prefix = PREFIXES.get(self.state['mode'], '')
        if self.props['handle_submit'](f"{prefix}{value}"):
            self.state.update({'text': '', 'mode': Mode.TEXT, 'autocomplete_matches': []})
            return True
        return False

    def contents(self) -> list[Component | None]:
        matching_commands = self.get_matching_commands()
        matching_models = self.get_matching_models()
        autocomplete_matches = self.state['autocomplete_matches']

        return [
            Box(border_color=Colors.HEX(COLORS.get(self.state['mode'], Theme.DARK_GRAY)), border_style=Borders.ROUND, flex=Flex.HORIZONTAL, margin={'top': 1})[
                Text(Colors.hex(PREFIXES.get(self.state['mode'], '>'), COLORS.get(self.state['mode'], Theme.GRAY)), margin={'left': 1, 'right': 1}, width=3),
                TextBox(
                    width=1.0,
                    text=self.state['text'],
                    history=self.props['history'],
                    placeholder=PLACEHOLDERS[self.state['mode']],
                    handle_input=self.handle_input,
                    handle_page=self.handle_page,
                    handle_change=self.handle_change,
                    handle_submit=self.handle_submit)
            ],
            Text(Colors.hex('Press Ctrl+C again to exit', Theme.GRAY), margin={'left': 2})
                if self.state['show_exit_prompt'] else
            CommandsList({match: '' for match in autocomplete_matches}, self.state['selected_idx'])
                if autocomplete_matches else
            CommandsList({model: MODELS_BY_NAME[model].api.display_name for model in matching_models}, self.state['selected_idx'])
                if matching_models else
            CommandsList(matching_commands, self.state['selected_idx'])
                if matching_commands else
            Box(flex=Flex.HORIZONTAL)[
                Text(self.get_shortcuts_text(), width=1.0, margin={'left': 2}),
                Text(Colors.hex(self.props['model'].api.display_name, Theme.WHITE)),
                Text(Colors.hex(self.props['model'].name, Theme.GRAY), margin={'left': 2, 'right': 2})
            ]
        ]
