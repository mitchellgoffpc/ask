from pathlib import Path
from typing import Callable, Any

from ask.ui.commands import CommandsList
from ask.ui.components import Component, Box, Text
from ask.ui.styles import Colors, Styles, Theme
from ask.ui.textbox import TextBox


class PromptTextBox(TextBox):
    def __init__(self, bash_mode: bool, handle_set_bash_mode: Callable[[bool], None], **props: Any) -> None:
        border_color = Theme.DARK_PINK if bash_mode else Theme.DARK_GRAY
        super().__init__(border_color=Colors.HEX(border_color), bash_mode=bash_mode, handle_set_bash_mode=handle_set_bash_mode, **props)

    def handle_input(self, ch: str) -> None:
        if self.props['bash_mode'] and not self.state['content'] and ch == '\x7f':
            self.props['handle_set_bash_mode'](False)
        elif not self.state['content'] and ch == '!':
            self.props['handle_set_bash_mode'](True)
        else:
            super().handle_input(ch)

    @property
    def content_width(self) -> int:
        return max(0, self.box_width - 5)  # 2 spaces for borders, 3 spaces for prompt arrow

    def render_contents(self) -> str:
        marker = Colors.hex('!', Theme.PINK) if self.props['bash_mode'] else '>'
        lines = super().render_contents().split('\n')
        lines = [f" {marker} {line}" if i == 0 else f"   {line}" for i, line in enumerate(lines)]
        return '\n'.join(lines)


class App(Component):
    initial_state = {'text': '', 'bash_mode': False}

    def handle_submit(self, value: str) -> None:
        pass

    def handle_change(self, value: str) -> None:
        self.state.update({'text': value})

    def handle_set_bash_mode(self, value: bool) -> None:
        self.state.update({'bash_mode': value})

    def contents(self) -> list[Component]:
        return [
            Box(padding={'left': 1, 'right': 1}, margin={'bottom': 1}, border_color=Colors.HEX(Theme.ORANGE))[
                Text(f"{Colors.hex('✻', Theme.ORANGE)} Welcome to {Styles.bold('Ask')}!", margin={'bottom': 1}),
                Text(Colors.hex("  /help for help", Theme.GRAY), margin={'bottom': 1}),
                Text(Colors.hex(f"  cwd: {Path.cwd()}", Theme.GRAY)),
            ],
            PromptTextBox(
                placeholder='Try "how do I log an error?"',
                bash_mode=self.state['bash_mode'],
                handle_change=self.handle_change,
                handle_submit=self.handle_submit,
                handle_set_bash_mode=self.handle_set_bash_mode),
            CommandsList(prefix=self.state['text'], bash_mode=self.state['bash_mode']),
        ]


# Entry point for testing

if __name__ == "__main__":
    from ask.ui.render import render_root
    app = App()
    render_root(app)
