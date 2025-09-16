import asyncio
import glob
import os
import re
import sys
import time
from base64 import b64decode
from dataclasses import replace
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

from ask.models import Model, Message, Content, Text as TextContent, Image, Reasoning, ToolRequest, ToolResponse, Command, Error
from ask.query import query
from ask.tools import TOOLS, Tool, ToolCallStatus, BashTool, EditTool, MultiEditTool, PythonTool, WriteTool
from ask.tools.read import read_file
from ask.ui.approvals import Approval
from ask.ui.commands import ShellCommand, SlashCommand, FilesCommand, InitCommand, get_usage_message
from ask.ui.components import Component, Box, Text, Line
from ask.ui.config import Config
from ask.ui.messages import PromptMessage, ResponseMessage, ErrorMessage, ToolCallMessage, ShellCommandMessage, SlashCommandMessage
from ask.ui.styles import Borders, Colors, Flex, Styles, Theme
from ask.ui.settings import ModelSelector
from ask.ui.textbox import TextBox

TOOL_REJECTED_MESSAGE = (
    "The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, "
    "the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.")

COMMANDS = {
    '/clear': 'Clear conversation history and free up context',
    '/cost': 'Show the total cost and token usage for current session',
    '/init': 'Generate an AGENTS.md file with codebase documentation',
    '/model': 'Select a model',
    '/exit': 'Exit the REPL',
    '/quit': 'Exit the REPL'}

def CommandName(name: str, active: bool) -> Text:
    return Text(Styles.bold(Colors.hex(name, Theme.BLUE if active else Theme.GRAY)))

def CommandDesc(desc: str, active: bool) -> Text:
    return Text(Colors.hex(desc, Theme.BLUE if active else Theme.GRAY))

def CommandsList(commands: dict[str, str], selected_idx: int) -> Box:
    return Box(flex=Flex.HORIZONTAL)[
        Box(margin={'left': 2})[(CommandName(cmd, idx == selected_idx) for idx, cmd in enumerate(commands.keys()))],
        Box(margin={'left': 3})[(CommandDesc(desc, idx == selected_idx) for idx, desc in enumerate(commands.values()))]
    ]


class Spinner(Box):
    initial_state = {'spinner_state': 0}
    frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    def handle_mount(self) -> None:
        super().handle_mount()
        asyncio.create_task(self.spin())

    async def spin(self) -> None:
        while self.mounted:
            self.state['spinner_state'] += 1
            await asyncio.sleep(0.25)

    def contents(self) -> list[Component | None]:
        spinner_text = f"{self.frames[self.state['spinner_state'] % len(self.frames)]} Waiting…"
        return [Text(Colors.hex(spinner_text, Theme.ORANGE), margin={'top': 1})]


class PromptTextBox(Box):
    initial_state = {'text': '', 'bash_mode': False, 'show_exit_prompt': False, 'selected_idx': 0, 'autocomplete_matches': []}

    def __init__(self, history: list[str], model: Model, handle_submit: Callable[[str], bool], handle_exit: Callable[[], None]) -> None:
        super().__init__(history=history, model=model, handle_submit=handle_submit, handle_exit=handle_exit)

    async def confirm_exit(self) -> None:
        if self.state['show_exit_prompt']:
            self.props['handle_exit']()
        else:
            self.state['show_exit_prompt'] = True
            await asyncio.sleep(1)
            self.state['show_exit_prompt'] = False

    def get_matching_commands(self) -> dict[str, str]:
        return {cmd: desc for cmd, desc in COMMANDS.items() if cmd.startswith(self.state['text']) or cmd == self.state['text'].rstrip(' ')}

    def get_current_word_prefix(self, text: str, cursor_pos: int) -> tuple[str, int]:
        if cursor_pos > len(text):
            cursor_pos = len(text)
        start = cursor_pos
        while start > 0 and text[start - 1] not in ' \t\n<>@|&;(){}[]"\'`':
            start -= 1
        return text[start:cursor_pos], start

    def find_path_matches(self, prefix: str) -> list[str]:
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

    def handle_raw_input(self, ch: str) -> None:
        if ch == '\x03':  # Ctrl+C
            self.state['text'] = ''
            asyncio.create_task(self.confirm_exit())

    def handle_input(self, ch: str, cursor_pos: int) -> bool:
        # Bash mode
        if cursor_pos == 0 and ch in ('\x7f', '\x1b\x7f'):
            self.state['bash_mode'] = False
        elif cursor_pos == 0 and ch == '!':
            self.state['bash_mode'] = True
            return False

        # Tab completion
        matching_commands = self.get_matching_commands()
        items = self.state['autocomplete_matches'] or (list(matching_commands.keys()) if matching_commands and self.state['text'] else [])
        if ch == '\t':
            if matching_commands and self.state['text']:
                self.state['text'] = list(matching_commands.keys())[self.state['selected_idx']] + ' '
                return False
            prefix, start_pos = self.get_current_word_prefix(self.state['text'], cursor_pos)
            matches = self.find_path_matches(prefix)
            if len(matches) == 1:
                completion = matches[0] + ('/' if (Path(prefix).parent / matches[0]).is_dir() else ' ')
                self.state['text'] = self.state['text'][:start_pos] + completion + self.state['text'][cursor_pos:]
                self.state['autocomplete_matches'] = []
            elif len(matches) > 1:
                if self.state['autocomplete_matches']:
                    self.state['selected_idx'] = (self.state['selected_idx'] + 1) % len(self.state['autocomplete_matches'])
                else:
                    self.state['autocomplete_matches'] = matches
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
        self.state['bash_mode'] = False

    def handle_change(self, value: str) -> None:
        if value.startswith('!'):
            value = value.removeprefix('!')
            self.state['bash_mode'] = True
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

        if self.state['text'] and (matching_commands := self.get_matching_commands()):
            value = list(matching_commands.keys())[self.state['selected_idx']]
        if self.props['handle_submit'](f"{'!' if self.state['bash_mode'] else ''}{value}"):
            self.state.update({'text': '', 'bash_mode': False, 'autocomplete_matches': []})
            return True
        return False

    def contents(self) -> list[Component | None]:
        bash_color = Theme.PINK if self.state['bash_mode'] else Theme.GRAY
        border_color = Theme.PINK if self.state['bash_mode'] else Theme.DARK_GRAY
        marker = Colors.hex('!', Theme.PINK) if self.state['bash_mode'] else '>'
        commands = self.get_matching_commands()
        autocomplete_matches = self.state['autocomplete_matches']

        return [
            Box(border_color=Colors.HEX(border_color), border_style=Borders.ROUND, flex=Flex.HORIZONTAL, margin={'top': 1})[
                Text(marker, margin={'left': 1, 'right': 1}, width=3),
                TextBox(
                    width=1.0,
                    text=self.state['text'],
                    history=self.props['history'],
                    placeholder="Try 'how do I log an error?'",
                    handle_input=self.handle_input,
                    handle_page=self.handle_page,
                    handle_change=self.handle_change,
                    handle_submit=self.handle_submit)
            ],
            Text(Colors.hex('Press Ctrl+C again to exit', Theme.GRAY), margin={'left': 2})
                if self.state['show_exit_prompt'] else
            CommandsList({match: '' for match in autocomplete_matches}, self.state['selected_idx'])
                if autocomplete_matches else
            CommandsList(commands, self.state['selected_idx'])
                if commands and self.state['text'] else
            Box(flex=Flex.HORIZONTAL)[
                Text(Colors.hex('! for bash mode', bash_color) + Colors.hex(' · / for commands', Theme.GRAY), width=1.0, margin={'left': 2}),
                Text(Colors.hex(self.props['model'].api.display_name, Theme.WHITE)),
                Text(Colors.hex(self.props['model'].name, Theme.GRAY), margin={'left': 2, 'right': 2})
            ]
        ]


class App(Box):
    initial_state = {'expanded': False, 'exiting': False, 'pending': 0, 'elapsed': 0, 'approvals': {}, 'show_model_selector': False}

    def __init__(self, model: Model, messages: dict[UUID, Message], tools: list[Tool], system_prompt: str) -> None:
        super().__init__(model=model, tools=tools, system_prompt=system_prompt)
        self.state['messages'] = messages
        self.state['model'] = model
        self.config = Config()
        self.tasks: list[asyncio.Task] = []
        self.start_time = time.monotonic()
        self.query_time = 0.

    def exit(self) -> None:
        self.state['exiting'] = True
        asyncio.get_running_loop().call_later(0.1, sys.exit, 0)

    def add_message(self, role: str, content: Content) -> UUID:
        message_uuid = uuid4()
        self.state['messages'] = self.state['messages'] | {message_uuid: Message(role=role, content=content)}
        return message_uuid

    def update_message(self, uuid: UUID, content: Content) -> None:
        self.state['messages'] = self.state['messages'] | {uuid: replace(self.state['messages'][uuid], content=content)}

    async def tick(self, interval: float) -> None:
        try:
            start_time = time.time()
            while True:
                self.state['elapsed'] = time.time() - start_time
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            self.state['elapsed'] = 0

    async def shell(self, command: str) -> None:
        ticker = asyncio.create_task(self.tick(1.0))
        shell_command = ShellCommand(command=command)
        message_uuid = self.add_message('user', shell_command)
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            status = ToolCallStatus.COMPLETED if process.returncode == 0 else ToolCallStatus.FAILED
            shell_command = replace(shell_command, stdout=stdout.decode().strip('\n'), stderr=stderr.decode().strip('\n'), status=status)
        except asyncio.CancelledError:
            shell_command = replace(shell_command, status=ToolCallStatus.CANCELLED)
        ticker.cancel()
        self.update_message(message_uuid, shell_command)

    async def query(self) -> None:
        self.state['pending'] += 1
        messages = self.state['messages'].copy()
        text, contents = '', {}
        start_time = time.monotonic()
        try:
            async for delta, content in query(self.state['model'], list(messages.values()), self.props['tools'], self.props['system_prompt']):
                text = text + delta
                if content:
                    contents[uuid4()] = content
                text_content = {uuid4(): TextContent(text)} if text and not any(isinstance(c, TextContent) for c in contents.values()) else {}
                if text or contents:
                    self.state['messages'] = messages | {uuid: Message(role='assistant', content=c) for uuid, c in (contents | text_content).items()}
        except asyncio.CancelledError:
            self.add_message('user', Error("Request interrupted by user"))
        except Exception as e:
            self.add_message('user', Error(str(e)))

        self.query_time += time.monotonic() - start_time
        try:
            tool_requests = {uuid: req for uuid, req in contents.items() if isinstance(req, ToolRequest)}
            if tool_requests:
                tasks = [asyncio.create_task(self.tool_call(req_uuid)) for req_uuid in tool_requests.keys()]
                await asyncio.gather(*tasks)
                await self.query()
            elif any(isinstance(c, Reasoning) for c in contents.values()) and not any(isinstance(c, TextContent) for c in contents.values()):
                await self.query()
        except asyncio.CancelledError:
            pass
        finally:
            self.state['pending'] -= 1

    async def tool_call(self, request_uuid: UUID) -> None:
        request = self.state['messages'][request_uuid].content
        try:
            tool = TOOLS[request.tool]
            args = tool.check(request.arguments)
            self.update_message(request_uuid, replace(request, processed_arguments=args))
            if tool.name in (BashTool.name, EditTool.name, MultiEditTool.name, PythonTool.name, WriteTool.name):
                future = asyncio.get_running_loop().create_future()
                self.state['approvals'] = self.state['approvals'] | {request_uuid: future}
                try:
                    await future
                finally:
                    self.state['approvals'] = {k:v for k,v in self.state['approvals'].items() if k != request_uuid}
            output = await tool.run(**args)
            output_content: TextContent | Image
            if args.get('file_type') == 'image':
                output_content = Image(data=b64decode(output), mimetype='image/jpeg')
            else:
                output_content = TextContent(output)
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=output_content, status=ToolCallStatus.COMPLETED)
        except asyncio.CancelledError:
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=TextContent(TOOL_REJECTED_MESSAGE), status=ToolCallStatus.CANCELLED)
            raise
        except Exception as e:
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=TextContent(str(e)), status=ToolCallStatus.FAILED)
        finally:
            self.add_message('user', response)

    def handle_mount(self) -> None:
        if self.state['messages']:
            prompt = list(self.state['messages'].values())[-1]
            if prompt.role == 'user' and isinstance(prompt.content, (TextContent, Command)):
                self.tasks.append(asyncio.create_task(self.query()))

    def handle_select_model(self, model: Model) -> None:
        if model != self.state['model']:
            # We have to remove all reasoning messages because they generally aren't compatible across models
            self.state['messages'] = {uuid: msg for uuid, msg in self.state['messages'].items() if not isinstance(msg.content, Reasoning)}
        self.state['model'] = model
        self.state['show_model_selector'] = False

    def handle_raw_input(self, ch: str) -> None:
        if ch == '\x03':  # Ctrl+C
            self.state.update({'show_model_selector': False, 'expanded': False})
        elif ch == '\x12':  # Ctrl+R
            self.state['expanded'] = not self.state['expanded']
        elif ch == '\x1b' and not self.state['approvals']:  # Escape key
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            self.tasks.clear()

    def handle_submit(self, value: str) -> bool:
        if any(not task.done() for task in self.tasks):
            return False

        self.config['history'] = [*self.config['history'], value]
        if value in ('/exit', '/quit', 'exit', 'quit'):
            self.exit()
        elif value == '/clear':
            self.state['messages'] = {}
        elif value == '/model':
            self.state['show_model_selector'] = True
        elif value == '/cost':
            output = get_usage_message(self.state['messages'], self.query_time, time.monotonic() - self.start_time)
            self.add_message('user', SlashCommand(command='/cost', output=output))
        elif value == '/init':
            self.add_message('user', InitCommand(command='/init'))
            self.tasks.append(asyncio.create_task(self.query()))
        elif value.startswith('!'):
            self.tasks.append(asyncio.create_task(self.shell(value.removeprefix('!'))))
        else:
            file_paths = [Path(m[1:]) for m in re.findall(r'@\S+', value) if Path(m[1:]).is_file()]  # get file attachments
            if file_paths:
                self.add_message('user', FilesCommand(command=value, file_contents={fp: read_file(fp) for fp in file_paths}))
            else:
                self.add_message('user', TextContent(value))
            self.tasks.append(asyncio.create_task(self.query()))
        return True

    def prompt_contents(self) -> Component:
        if self.state['exiting']:
            wall_time = time.monotonic() - self.start_time
            return Text(Colors.hex(get_usage_message(self.state['messages'], self.query_time, wall_time), Theme.GRAY), margin={'top': 1})
        elif approval_uuid := next(iter(self.state['approvals'].keys()), None):
            return Approval(
                tool_call=self.state['messages'][approval_uuid].content,
                future=self.state['approvals'][approval_uuid]
            )
        elif self.state['show_model_selector']:
            return ModelSelector(
                active_model=self.state['model'],
                handle_select=self.handle_select_model
            )
        elif self.state['expanded']:
            return Box()[
                Line(width=1.0, color=Colors.HEX(Theme.GRAY), margin={'top': 1}),
                Text(Colors.hex('  Showing detailed transcript · Ctrl+R to toggle', Theme.GRAY))
            ]
        else:
            return PromptTextBox(
                history=self.config['history'],
                model=self.state['model'],
                handle_submit=self.handle_submit,
                handle_exit=self.exit
            )

    def contents(self) -> list[Component | None]:
        tool_responses = {msg.content.call_id: msg.content for msg in self.state['messages'].values() if isinstance(msg.content, ToolResponse)}
        messages = []
        for msg in self.state['messages'].values():
            match (msg.role, msg.content):
                case ('user', TextContent()):
                    messages.append(PromptMessage(text=msg.content))
                case ('user', Error()):
                    messages.append(ErrorMessage(error=msg.content))
                case ('user', ShellCommand()):
                    messages.append(ShellCommandMessage(command=msg.content, elapsed=self.state['elapsed'], expanded=self.state['expanded']))
                case ('user', SlashCommand()):
                    messages.append(SlashCommandMessage(command=msg.content))
                case ('assistant', TextContent()):
                    messages.append(ResponseMessage(text=msg.content))
                case ('assistant', ToolRequest()):
                    messages.append(ToolCallMessage(request=msg.content, response=tool_responses.get(msg.content.call_id), expanded=self.state['expanded']))
                case _:
                    pass

        return [
            *messages,
            Spinner() if self.state['pending'] else None,
            self.prompt_contents(),
        ]
