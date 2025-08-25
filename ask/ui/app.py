import asyncio
import sys
import time
from dataclasses import replace
from typing import Callable
from uuid import UUID, uuid4

from ask.models import Model, Message, Content, Text as TextContent, TextPrompt, ToolRequest, ToolResponse, ShellCommand, Status
from ask.query import query
from ask.tools import TOOLS, Tool
from ask.ui.approvals import Approval
from ask.ui.components import Component, Box, Text, Line
from ask.ui.config import Config
from ask.ui.messages import Prompt, TextResponse, ToolCall, ShellCall
from ask.ui.styles import Borders, Colors, Flex, Styles, Theme
from ask.ui.textbox import TextBox

TOOL_REJECTED_MESSAGE = (
    "The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, "
    "the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.")
COMMANDS = {
    '/clear': 'Clear conversation history and free up context',
    '/exit': 'Exit the REPL',
    '/quit': 'Exit the REPL'}

def is_pending(message: Message) -> bool:
    return isinstance(message.content, (TextPrompt, ToolResponse)) and message.content.status is Status.PENDING

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
    initial_state = {'text': '', 'bash_mode': False, 'selected_idx': 0}

    def __init__(self, history: list[str], handle_submit: Callable[[str], bool]) -> None:
        super().__init__(history=history, handle_submit=handle_submit)

    def get_matching_commands(self) -> dict[str, str]:
        return {cmd: desc for cmd, desc in COMMANDS.items() if cmd.startswith(self.state['text'])}

    def handle_input(self, ch: str, cursor_pos: int) -> bool:
        # Bash mode
        if cursor_pos == 0 and ch in ('\x7f', '\x1b\x7f'):
            self.state['bash_mode'] = False
        elif cursor_pos == 0 and ch == '!':
            self.state['bash_mode'] = True
            return False

        # Command selection
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

    def handle_page(self, _: int) -> None:
        self.state['bash_mode'] = False

    def handle_change(self, value: str) -> None:
        if value.startswith('!'):
            value = value.removeprefix('!')
            self.state['bash_mode'] = True
        if value != self.state['text']:
            self.state['selected_idx'] = 0
        self.state['text'] = value

    def handle_submit(self, value: str) -> None:
        if self.props['handle_submit'](f"{'!' if self.state['bash_mode'] else ''}{value}"):
            self.state['text'] = ''
            self.state['bash_mode'] = False

    def contents(self) -> list[Component | None]:
        border_color = Theme.PINK if self.state['bash_mode'] else Theme.DARK_GRAY
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
                    handle_page=self.handle_page,
                    handle_change=self.handle_change,
                    handle_submit=self.handle_submit)
            ],
            CommandsList(commands, self.state['selected_idx']) if commands and self.state['text'] else Shortcuts(self.state['bash_mode'])
        ]


class App(Box):
    initial_state = {'expanded': False, 'elapsed': 0, 'approvals': {}}

    def __init__(self, model: Model, messages: dict[UUID, Message], tools: list[Tool], system_prompt: str) -> None:
        super().__init__(model=model, tools=tools, system_prompt=system_prompt)
        self.state['messages'] = messages
        self.config = Config()
        self.tasks: list[asyncio.Task] = []
        self.tool_responses: dict[str, ToolResponse] = {}
        for msg in messages.values():
            if isinstance(msg.content, ToolResponse):
                self.tool_responses[msg.content.call_id] = msg.content

    async def tick(self, interval: float) -> None:
        try:
            start_time = time.time()
            while True:
                self.state['elapsed'] = time.time() - start_time
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            self.state['elapsed'] = 0

    async def shell(self, message_uuid: UUID, command: str) -> None:
        ticker = asyncio.create_task(self.tick(1.0))
        message = self.state['messages'][message_uuid]
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            shell_command = replace(message.content, output=stdout.decode(), error=stderr.decode(), status=Status.COMPLETED)
        except asyncio.CancelledError:
            shell_command = replace(message.content, status=Status.CANCELLED)
        finally:
            ticker.cancel()
        self.update_message(message_uuid, shell_command)

    async def query(self, prompt_uuid: UUID) -> None:
        messages = self.state['messages'].copy()
        prompt = messages[prompt_uuid].content
        try:
            text = ''
            contents = {}
            async for delta, content in query(self.props['model'], list(messages.values()), self.props['tools'], self.props['system_prompt']):
                text = text + delta
                if content:
                    contents[uuid4()] = content
                text_content = {uuid4(): TextContent(text)} if text and not any(isinstance(c, TextContent) for c in contents.values()) else {}
                if text or contents:
                    self.state['messages'] = messages | {uuid: Message(role='assistant', content=c) for uuid, c in (contents | text_content).items()}

            tool_requests = {uuid: req for uuid, req in contents.items() if isinstance(req, ToolRequest)}
            tool_responses = {uuid4(): ToolResponse(call_id=req.call_id, tool=req.tool, response='', status=Status.PENDING) for req in tool_requests.values()}
            self.state['messages'] = self.state['messages'] | {uuid: Message(role='user', content=resp) for uuid, resp in tool_responses.items()}
            if tool_requests:
                tasks = [asyncio.create_task(self.tool_call(req_uuid, resp_uuid)) for req_uuid, resp_uuid in zip(tool_requests, tool_responses, strict=True)]
                self.tasks.extend([*tasks, asyncio.create_task(self.send_tool_responses(prompt_uuid, tasks))])
            else:
                self.update_message(prompt_uuid, replace(prompt, status=Status.COMPLETED))
        except asyncio.CancelledError:
            self.update_message(prompt_uuid, replace(prompt, status=Status.CANCELLED, error="Request interrupted by user"))
        except Exception as e:
            self.update_message(prompt_uuid, replace(prompt, status=Status.FAILED, error=str(e)))

    async def tool_call(self, request_uuid: UUID, response_uuid: UUID) -> None:
        request = self.state['messages'][request_uuid].content
        try:
            tool = TOOLS[request.tool]
            args = tool.check(request.arguments)
            self.update_message(request_uuid, replace(request, processed_arguments=args))
            if tool in (TOOLS['Bash'], TOOLS['Edit'], TOOLS['Python'], TOOLS['Write']):
                future = asyncio.get_running_loop().create_future()
                self.state['approvals'] = self.state['approvals'] | {request_uuid: future}
                try:
                    await future
                finally:
                    self.state['approvals'] = {k:v for k,v in self.state['approvals'].items() if k != request_uuid}
            output = await tool.run(**args)
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=output, status=Status.COMPLETED)
        except asyncio.CancelledError:
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=TOOL_REJECTED_MESSAGE, status=Status.CANCELLED)
            raise
        except Exception as e:
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=str(e), status=Status.FAILED)
        finally:
            self.tool_responses[request.call_id] = response
            self.update_message(response_uuid, response)

    async def send_tool_responses(self, prompt_uuid: UUID, tool_call_tasks: list[asyncio.Task]) -> None:
        try:
            await asyncio.gather(*tool_call_tasks)
            self.tasks.append(asyncio.create_task(self.query(prompt_uuid)))
        except asyncio.CancelledError:
            self.update_message(prompt_uuid, replace(self.state['messages'][prompt_uuid].content, status=Status.COMPLETED))

    def update_message(self, uuid: UUID, content: Content) -> None:
        self.state['messages'] = self.state['messages'] | {uuid: replace(self.state['messages'][uuid], content=content)}

    def handle_mount(self) -> None:
        if self.state['messages']:
            prompt_uuid, prompt = list(self.state['messages'].items())[-1]
            if prompt.role == 'user' and isinstance(prompt.content, TextPrompt):
                self.tasks.append(asyncio.create_task(self.query(prompt_uuid)))

    def handle_submit(self, value: str) -> bool:
        if any(not task.done() for task in self.tasks):
            return False

        self.config['history'] = [*self.config['history'], value]
        if value in ('/exit', '/quit', 'exit', 'quit'):
            sys.exit()
        elif value == '/clear':
            self.state['messages'] = {}
        elif value.startswith('!'):
            value = value.removeprefix('!')
            cmd_uuid, cmd = uuid4(), ShellCommand(command=value, output='', error='', status=Status.PENDING)
            self.state['messages'] = self.state['messages'] | {cmd_uuid: Message(role='user', content=cmd)}
            self.tasks.append(asyncio.create_task(self.shell(cmd_uuid, value)))
        else:
            prompt_uuid = uuid4()
            self.state['messages'] = self.state['messages'] | {prompt_uuid: Message(role='user', content=TextPrompt(value))}
            self.tasks.append(asyncio.create_task(self.query(prompt_uuid)))
        return True

    def handle_raw_input(self, ch: str) -> None:
        if ch == '\x12':  # Ctrl+R
            self.state['expanded'] = not self.state['expanded']
        elif ch == '\x1b' and not self.state['approvals']:  # Escape key
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            self.tasks.clear()

    def render_message(self, role: str, content: Content) -> Component | None:
        if role == 'user':
            if isinstance(content, TextPrompt):
                return Prompt(text=content)
            elif isinstance(content, ShellCommand):
                return ShellCall(command=content, elapsed=self.state['elapsed'], expanded=self.state['expanded'])
        elif role == 'assistant':
            if isinstance(content, TextContent):
                return TextResponse(text=content)
            elif isinstance(content, ToolRequest):
                response = self.tool_responses.get(content.call_id)
                return ToolCall(request=content, response=response, expanded=self.state['expanded'])
        return None

    def contents(self) -> list[Component | None]:
        approval_uuid = next(iter(self.state['approvals'].keys()), None)
        waiting = any(is_pending(msg) for msg in self.state['messages'].values()) and not self.state['approvals']
        messages = [self.render_message(msg.role, msg.content) for msg in self.state['messages'].values()]

        return [
            *filter(None, messages),
            Spinner() if waiting else None,

            Box()[
                Line(width=1.0, color=Colors.HEX(Theme.GRAY), margin={'top': 1}),
                Text(Colors.hex('  Showing detailed transcript · Ctrl+R to toggle', Theme.GRAY))
            ] if self.state['expanded'] else
            Approval(
                tool_call=self.state['messages'][approval_uuid].content,
                future=self.state['approvals'][approval_uuid]
            ) if approval_uuid else
            PromptTextBox(
                history=self.config['history'],
                handle_submit=self.handle_submit
            ),
        ]
