import sys
import time
from dataclasses import replace
from requests import ConnectionError
from typing import Any

from ask.models import Model, Message, Content, Text as TextContent, ToolRequest, ToolResponse
from ask.query import query
from ask.tools import TOOLS, Tool
from ask.ui.components import Component, Box, Text, TextCallback, BoolCallback, asyncronous
from ask.ui.config import Config
from ask.ui.messages import Prompt, TextResponse, ToolCall
from ask.ui.styles import Borders, Colors, Flex, Styles, Theme
from ask.ui.textbox import TextBox

MAX_RETRIES = 5
COMMANDS = {
    '/clear': 'Clear conversation history and free up context',
    '/exit': 'Exit the REPL',
    '/quit': 'Exit the REPL'}

def Shortcuts(bash_mode: bool) -> Text:
    bash_color = Theme.PINK if bash_mode else Theme.GRAY
    return Text(Colors.hex('! for bash mode', bash_color) + Colors.hex(' · / for commands', Theme.GRAY), margin={'left': 2})

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
    initial_state = {'selected_idx': 0}

    def __init__(self, bash_mode: bool, handle_set_text: TextCallback, handle_set_bash_mode: BoolCallback, **props: Any) -> None:
        super().__init__(bash_mode=bash_mode, handle_set_text=handle_set_text, handle_set_bash_mode=handle_set_bash_mode, **props)

    def get_matching_commands(self, prefix: str) -> dict[str, str]:
        return {cmd: desc for cmd, desc in COMMANDS.items() if cmd.startswith(prefix)}

    def handle_update(self, new_props: dict[str, Any]) -> None:
        if new_props['text'] != self.props['text']:
            self.state['selected_idx'] = 0

    def handle_input(self, ch: str) -> bool:
        if self.props['bash_mode'] and not self.props['text'] and ch == '\x7f':
            self.props['handle_set_bash_mode'](False)
        elif not self.props['bash_mode'] and not self.props['text'] and ch == '!':
            self.props['handle_set_bash_mode'](True)
            return False

        matching_commands = self.get_matching_commands(self.props['text'])
        selected_idx = self.state['selected_idx']
        if not self.props['text'] or not matching_commands:
            return True
        elif ch in ('\t', '\r') and matching_commands:
            command = list(matching_commands.keys())[selected_idx]
            if ch == '\t':
                self.props['handle_set_text'](command)
            else:
                self.props['handle_submit'](command)
            return False
        elif ch in ('\x1b[A', '\x10'):  # Up arrow or Ctrl+P
            selected_idx -= 1
        elif ch in ('\x1b[B', '\x0e'):  # Down arrow or Ctrl+N
            selected_idx += 1
        if selected_idx != self.state['selected_idx']:
            self.state['selected_idx'] = selected_idx % len(matching_commands)
            return False
        return True

    def contents(self) -> list[Component]:
        border_color = Theme.DARK_PINK if self.props['bash_mode'] else Theme.DARK_GRAY
        marker = Colors.hex('!', Theme.PINK) if self.props['bash_mode'] else '>'
        commands = self.get_matching_commands(self.props['text'])
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
            ],
            CommandsList(commands, self.state['selected_idx']) if commands and self.props['text'] else Shortcuts(self.props['bash_mode'])
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
    initial_state = {'text': '', 'loading': False, 'bash_mode': False}

    def __init__(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str, **props: Any) -> None:
        super().__init__(model=model, tools=tools, system_prompt=system_prompt, **props)
        self.state['messages'] = messages
        self.config = Config()
        self.tool_responses: dict[str, ToolResponse] = {}

        if self.state['messages'] and self.state['messages'][-1].role == 'user':
            user_messages = [content.text for content in self.state['messages'][-1].content if isinstance(content, TextContent)]
            self.config['history'] = self.config['history'] + user_messages
            self.query()

    @asyncronous
    def query(self) -> None:
        self.state['loading'] = True
        try:
            backoff = 1
            for i in range(MAX_RETRIES):
                try:
                    text = ''
                    contents = []
                    history = self.state['messages'][:]
                    for delta, content in query(self.props['model'], self.state['messages'], self.props['tools'], self.props['system_prompt']):
                        text = text + delta
                        contents.extend([content] if content else [])
                        text_content = [TextContent(text)] if text and not any(isinstance(c, TextContent) for c in contents) else []
                        if text or contents:
                            message = Message(role='assistant', content=[*text_content, *contents], errors=[])
                            self.state['messages'] = [*history, message]

                    tool_responses: list[Content] = []
                    for content in contents:
                        if isinstance(content, ToolRequest):
                            tool = TOOLS[content.tool]
                            response = tool.run(content.arguments)
                            tool_response = ToolResponse(call_id=content.call_id, tool=content.tool, response=response)
                            tool_responses.append(tool_response)
                            self.tool_responses[content.call_id] = tool_response

                    if tool_responses:
                        self.state['messages'] = [*self.state['messages'], Message(role='user', content=tool_responses)]
                    else:
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
            self.state['messages'] = [*self.state['messages'], Message(role='user', content=[TextContent(value)])]
            self.query()

    def handle_set_text(self, value: str) -> None:
        self.state['text'] = value

    def handle_set_bash_mode(self, value: bool) -> None:
        self.state['bash_mode'] = value

    def handle_textbox_input(self, ch: str) -> bool:
        if self.state['text'].startswith('/') and ch in ('\x1b[A', '\x1b[B'):  # Arrow keys
            return False
        return True

    def render_message(self, message: Message) -> list[Component]:
        components = []
        if message.role == 'user':
            for content in message.content:
                if isinstance(content, TextContent):
                    components.append(Prompt(content.text, errors=message.errors))
        elif message.role == 'assistant':
            for content in message.content:
                if isinstance(content, TextContent):
                    components.append(TextResponse(content.text))
                elif isinstance(content, ToolRequest):
                    response = self.tool_responses.get(content.call_id)
                    result = response.response if response else None
                    components.append(ToolCall(tool=content.tool, args=content.arguments, result=result))
        return components

    def contents(self) -> list[Component]:
        return [
            *[component for message in self.state['messages'] for component in self.render_message(message)],
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
        ]
