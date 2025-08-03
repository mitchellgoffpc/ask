import time
from dataclasses import replace
from pathlib import Path
from typing import Callable
from requests import ConnectionError

from ask.models import MODEL_SHORTCUTS, Message, Text as TextContent
from ask.query import query
from ask.ui.commands import CommandsList
from ask.ui.components import Component, Box, Text, asyncronous
from ask.ui.messages import Prompt, TextResponse
from ask.ui.styles import Borders, Colors, Styles, Theme, Flex
from ask.ui.textbox import TextBox, TextCallback

MAX_RETRIES = 10

BoolCallback = Callable[[bool], None]

class PromptTextBox(Box):
    def __init__(self, text: str, placeholder: str, bash_mode: bool,
                       handle_submit: TextCallback, handle_set_text: TextCallback, handle_set_bash_mode: BoolCallback) -> None:
        super().__init__(text=text, placeholder=placeholder, bash_mode=bash_mode,
                         handle_set_text=handle_set_text, handle_set_bash_mode=handle_set_bash_mode, handle_submit=handle_submit)

    def handle_input(self, ch: str) -> None:
        if self.props['bash_mode'] and not self.props['text'] and ch == '\x7f':
            self.props['handle_set_bash_mode'](False)

    def handle_set_text(self, text: str) -> None:
        if text == '!':
            self.props['handle_set_bash_mode'](True)
            self.props['handle_set_text']("")
        else:
            self.props['handle_set_text'](text)

    def contents(self) -> list[Component]:
        border_color = Theme.DARK_PINK if self.props['bash_mode'] else Theme.DARK_GRAY
        marker = Colors.hex('!', Theme.PINK) if self.props['bash_mode'] else '>'
        return [
            Box(border_color=Colors.HEX(border_color), border_style=Borders.SINGLE, flex=Flex.HORIZONTAL)[
                Text(marker, margin={'left': 1, 'right': 1}, width=3),
                TextBox(
                    width=1.0,
                    text=self.props['text'],
                    placeholder=self.props.get('placeholder', 'Type your message here...'),
                    handle_submit=self.props['handle_submit'],
                    handle_change=self.handle_set_text)
            ]
        ]


class Spinner(Box):
    initial_state = {'spinner_state': 0}

    def handle_mount(self):
        super().handle_mount()
        self.spin()

    @asyncronous
    def spin(self):
        while self.mounted:
            self.state['spinner_state'] += 1
            time.sleep(0.5)

    def contents(self):
        return [Text(f"Loading {self.state['spinner_state'] % 4 * '.'}", margin={'bottom': 1})]


class App(Box):
    initial_state = {'messages': [], 'text': '', 'loading': False, 'bash_mode': False}

    @asyncronous
    def handle_submit(self, value: str) -> None:
        self.state['text'] = ''
        self.state['loading'] = True
        self.state['messages'] = [*self.state['messages'], Message(role='user', content=[TextContent(value)])]
        try:
            backoff = 1
            for i in range(MAX_RETRIES):
                try:
                    for _, content in query(MODEL_SHORTCUTS['sonnet'], self.state['messages'], [], "You are a helpful assistant."):
                        if content:
                            self.state['messages'] = [*self.state['messages'], Message(role='assistant', content=[content])]
                    return
                except ConnectionError:
                    last_message = self.state['messages'][-1]
                    error_message = f'Connection Error - Retrying in {backoff} seconds (attempt {i} / {MAX_RETRIES})'
                    self.state['messages'] = [*self.state['messages'][:-1], replace(last_message, errors=[*last_message.errors, error_message])]
                    time.sleep(backoff)
                    backoff *= 2
        finally:
            self.state['loading'] = False

    def handle_set_text(self, value: str) -> None:
        self.state['text'] = value

    def handle_set_bash_mode(self, value: bool) -> None:
        self.state['bash_mode'] = value

    def render_message(self, message: Message) -> Component:
        if message.role == 'user':
            assert isinstance(message.content[0], TextContent)
            return Prompt(message.content[0].text, errors=message.errors)
        elif message.role == 'assistant':
            if isinstance(message.content[0], TextContent):
                return TextResponse(message.content[0].text)
        raise NotImplementedError(f"Unsupported message content type: {type(message.content[0])}")

    def contents(self) -> list[Component]:
        return [
            Box(padding={'left': 1, 'right': 1}, margin={'bottom': 1}, border_color=Colors.HEX(Theme.ORANGE), border_style=Borders.ROUND)[
                Text(f"{Colors.hex('✻', Theme.ORANGE)} Welcome to {Styles.bold('Ask')}!", margin={'bottom': 1}),
                Text(Colors.hex("  /help for help", Theme.GRAY), margin={'bottom': 1}),
                Text(Colors.hex(f"  cwd: {Path.cwd()}", Theme.GRAY)),
            ],
            *[self.render_message(message) for message in self.state['messages']],
            *([Spinner()] if self.state['loading'] else []),
            PromptTextBox(
                text=self.state['text'],
                placeholder='Try "how do I log an error?"',
                bash_mode=self.state['bash_mode'],
                handle_submit=self.handle_submit,
                handle_set_text=self.handle_set_text,
                handle_set_bash_mode=self.handle_set_bash_mode),
            CommandsList(prefix=self.state['text'], bash_mode=self.state['bash_mode']),
        ]


# Entry point for testing

if __name__ == "__main__":
    from ask.ui.render import render_root
    app = App()
    render_root(app)
