import sys
import time
from dataclasses import replace
from requests import ConnectionError

from ask.models import Model, Message, Content, Text as TextContent, ToolRequest, ToolResponse
from ask.query import query
from ask.tools import TOOLS, Tool
from ask.ui.components import Component, Box, Text, Line, TextCallback, asyncronous
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
    initial_state = {'text': '', 'bash_mode': False, 'selected_idx': 0}

    def __init__(self, history: list[str], handle_submit: TextCallback) -> None:
        super().__init__(history=history, handle_submit=handle_submit)

    def get_matching_commands(self) -> dict[str, str]:
        return {cmd: desc for cmd, desc in COMMANDS.items() if cmd.startswith(self.state['text'])}

    def handle_input(self, ch: str) -> bool:
        if self.state['bash_mode'] and not self.state['text'] and ch == '\x7f':
            self.state['bash_mode'] = False
        elif not self.state['bash_mode'] and not self.state['text'] and ch == '!':
            self.state['bash_mode'] = True
            return False

        matching_commands = self.get_matching_commands()
        selected_idx = self.state['selected_idx']
        if not self.state['text'] or not matching_commands:
            return True
        elif ch in ('\t', '\r') and matching_commands:
            command = list(matching_commands.keys())[selected_idx]
            if ch == '\t':
                self.state['text'] = command
            else:
                self.handle_submit(command)
            return False
        elif ch in ('\x1b[A', '\x10'):  # Up arrow or Ctrl+P
            selected_idx -= 1
        elif ch in ('\x1b[B', '\x0e'):  # Down arrow or Ctrl+N
            selected_idx += 1
        if selected_idx != self.state['selected_idx']:
            self.state['selected_idx'] = selected_idx % len(matching_commands)
            return False
        return True

    def handle_change(self, value: str) -> None:
        if value != self.state['text']:
            self.state['selected_idx'] = 0
        self.state['text'] = value

    def handle_submit(self, value: str) -> None:
        self.state['text'] = ''
        self.props['handle_submit'](value)

    def contents(self) -> list[Component | None]:
        border_color = Theme.DARK_PINK if self.state['bash_mode'] else Theme.DARK_GRAY
        marker = Colors.hex('!', Theme.PINK) if self.state['bash_mode'] else '>'
        commands = self.get_matching_commands()
        return [
            Box(border_color=Colors.HEX(border_color), border_style=Borders.ROUND, flex=Flex.HORIZONTAL, margin={'top': 1})[
                Text(marker, margin={'left': 1, 'right': 1}, width=3),
                TextBox(
                    width=1.0,
                    text=self.state['text'],
                    history=self.props['history'],
                    placeholder="Try 'how do I log an error?'",
                    handle_input=self.handle_input,
                    handle_change=self.handle_change,
                    handle_submit=self.handle_submit)
            ],
            CommandsList(commands, self.state['selected_idx']) if commands and self.state['text'] else Shortcuts(self.state['bash_mode'])
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

    def contents(self) -> list[Component | None]:
        spinner_text = f"{self.frames[self.state['spinner_state'] % len(self.frames)]} Waiting…"
        return [Text(Colors.hex(spinner_text, Theme.ORANGE), margin={'top': 1})]


class App(Box):
    initial_state = {'loading': False, 'expanded': False}

    def __init__(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> None:
        super().__init__(model=model, tools=tools, system_prompt=system_prompt)
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
        backoff, retries = 1, 0
        while True:
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
                    backoff, retries = 1, 0
                else:
                    break

            except ConnectionError:
                if retries >= MAX_RETRIES:
                    break
                last_message = self.state['messages'][-1]
                error_message = f'Connection Error - Retrying in {backoff} seconds (attempt {retries+1} / {MAX_RETRIES})'
                self.state['messages'] = [*self.state['messages'][:-1], replace(last_message, errors=[*last_message.errors, error_message])]
                time.sleep(backoff)
                backoff *= 2
                retries += 1

        self.state['loading'] = False

    def handle_submit(self, value: str) -> None:
        self.config['history'] = [*self.config['history'], value]
        if value in ('/exit', '/quit'):
            sys.exit()
        elif value == '/clear':
            self.state['messages'] = []
        else:
            self.state['messages'] = [*self.state['messages'], Message(role='user', content=[TextContent(value)])]
            self.query()

    def handle_raw_input(self, ch: str) -> None:
        if ch == '\x12':  # Ctrl+R
            self.state['expanded'] = not self.state['expanded']

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
                    components.append(ToolCall(tool=content.tool, args=content.arguments, result=result, expanded=self.state['expanded']))
        return components

    def contents(self) -> list[Component | None]:
        return [
            *[component for message in self.state['messages'] for component in self.render_message(message)],
            Spinner() if self.state['loading'] else None,
            PromptTextBox(
                history=self.config['history'],
                handle_submit=self.handle_submit,
            ) if not self.state['expanded'] else None,
            Box()[
                Line(width=1.0, color=Colors.HEX(Theme.GRAY), margin={'top': 1}),
                Text(Colors.hex('  Showing detailed transcript · Ctrl+R to toggle', Theme.GRAY)),
            ] if self.state['expanded'] else None
        ]
