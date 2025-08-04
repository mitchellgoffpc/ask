import sys
import time
from typing import Any, cast
from dataclasses import replace
from requests import ConnectionError

from ask.models import MODEL_SHORTCUTS, Message, Text as TextContent
from ask.query import query
from ask.ui.commands import CommandsList
from ask.ui.components import Component, Box, Text, TextCallback, BoolCallback, asyncronous
from ask.ui.config import Config
from ask.ui.messages import Prompt, TextResponse
from ask.ui.styles import Borders, Colors, Theme, Flex
from ask.ui.textbox import TextBox, InputCallback

MAX_RETRIES = 10

class PromptTextBox(Box):
    def __init__(self, bash_mode: bool, handle_input: InputCallback, handle_set_text: TextCallback, handle_set_bash_mode: BoolCallback, **props: Any) -> None:
        super().__init__(bash_mode=bash_mode, handle_input=handle_input, handle_set_text=handle_set_text, handle_set_bash_mode=handle_set_bash_mode, **props)

    def handle_input(self, ch: str) -> bool:
        if self.props['bash_mode'] and not self.props['text'] and ch == '\x7f':
            self.props['handle_set_bash_mode'](False)
        elif not self.props['bash_mode'] and not self.props['text'] and ch == '!':
            self.props['handle_set_bash_mode'](True)
            return False
        return cast(bool, self.props['handle_input'](ch))

    def contents(self) -> list[Component]:
        border_color = Theme.DARK_PINK if self.props['bash_mode'] else Theme.DARK_GRAY
        marker = Colors.hex('!', Theme.PINK) if self.props['bash_mode'] else '>'
        return [
            Box(border_color=Colors.HEX(border_color), border_style=Borders.SINGLE, flex=Flex.HORIZONTAL, margin={'top': 1})[
                Text(marker, margin={'left': 1, 'right': 1}, width=3),
                TextBox(
                    width=1.0,
                    text=self.props['text'],
                    history=self.props.get('history'),
                    placeholder=self.props.get('placeholder', 'Type your message here...'),
                    handle_input=self.handle_input,
                    handle_submit=self.props['handle_submit'],
                    handle_change=self.props['handle_set_text'])
            ]
        ]


class Spinner(Box):
    initial_state = {'spinner_state': 0}
    frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    def handle_mount(self) -> None:
        super().handle_mount()
        self.spin()

    @asyncronous
    def spin(self) -> None:
        while self.mounted:
            self.state['spinner_state'] += 1
            time.sleep(0.25)

    def contents(self) -> list[Component]:
        spinner_text = f"{self.frames[self.state['spinner_state'] % len(self.frames)]} Waiting…"
        return [Text(Colors.hex(spinner_text, Theme.ORANGE), margin={'top': 1})]


class App(Box):
    initial_state = {'messages': [], 'text': '', 'loading': False, 'bash_mode': False}
    config = Config()

    @asyncronous
    def query(self, value: str) -> None:
        self.state['messages'] = [*self.state['messages'], Message(role='user', content=[TextContent(value)])]
        self.state['loading'] = True
        try:
            backoff = 1
            for i in range(MAX_RETRIES):
                try:
                    text = ''
                    response = Message(role='assistant', content=[])
                    history = self.state['messages'][:]
                    for delta, content in query(MODEL_SHORTCUTS['sonnet'], self.state['messages'], [], "You are a helpful assistant."):
                        text = text + delta
                        response = replace(response, content=[TextContent(text)])
                        if content:
                            response = replace(response, content=[content])
                        self.state['messages'] = [*history, response]
                    return
                except ConnectionError:
                    last_message = self.state['messages'][-1]
                    error_message = f'Connection Error - Retrying in {backoff} seconds (attempt {i} / {MAX_RETRIES})'
                    self.state['messages'] = [*self.state['messages'][:-1], replace(last_message, errors=[*last_message.errors, error_message])]
                    time.sleep(backoff)
                    backoff *= 2
        finally:
            self.state['loading'] = False

    def handle_submit(self, value: str) -> None:
        self.config['history'] = [*self.config['history'], value]
        self.state['text'] = ''
        if value in ('/exit', '/quit'):
            sys.exit()
        elif value == '/clear':
            self.state['messages'] = []
        else:
            self.query(value)

    def handle_set_text(self, value: str) -> None:
        self.state['text'] = value

    def handle_set_bash_mode(self, value: bool) -> None:
        self.state['bash_mode'] = value

    def handle_autocomplete(self, command: str) -> None:
        self.state['text'] = command

    def handle_textbox_input(self, ch: str) -> bool:
        if self.state['text'].startswith('/') and ch in ('\x1b[A', '\x1b[B'):  # Arrow keys
            return False
        return True

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
            *[self.render_message(message) for message in self.state['messages']],
            *([Spinner()] if self.state['loading'] else []),
            PromptTextBox(
                text=self.state['text'],
                placeholder='Try "how do I log an error?"',
                history=self.config['history'],
                bash_mode=self.state['bash_mode'],
                handle_input=self.handle_textbox_input,
                handle_submit=self.handle_submit,
                handle_set_text=self.handle_set_text,
                handle_set_bash_mode=self.handle_set_bash_mode),
            CommandsList(prefix=self.state['text'], bash_mode=self.state['bash_mode'], handle_autocomplete=self.handle_autocomplete),
        ]
