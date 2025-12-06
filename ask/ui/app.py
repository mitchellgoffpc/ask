from __future__ import annotations
import asyncio
import os
import re
import shlex
import sys
import time
from base64 import b64decode
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID, uuid4
from typing import Any, ClassVar

from ask.models import MODELS_BY_NAME, Model, Message, Content, Text as TextContent, Image, Reasoning, ToolRequest, ToolResponse, Error
from ask.prompts import get_agents_md_path
from ask.query import query
from ask.shells import PYTHON_SHELL
from ask.tools import TOOLS, Tool, ToolCallStatus, BashTool, EditTool, MultiEditTool, PythonTool, ToDoTool, WriteTool
from ask.tools.read import read_file
from ask.ui.core.components import Component, Controller, Box, Text, Widget, dirty
from ask.ui.core.cursor import hide_cursor
from ask.ui.core.styles import Colors, Theme
from ask.ui.dialogs import ApprovalDialog, EditApprovalController
from ask.ui.commands import BashCommand, FilesCommand, InitCommand, MemorizeCommand, PythonCommand, SlashCommand, get_usage_message
from ask.ui.config import Config, History
from ask.ui.messages import ErrorMessage, PromptMessage, ResponseMessage, ToolCallMessage
from ask.ui.messages import BashCommandMessage, MemorizeCommandMessage, PythonCommandMessage, SlashCommandMessage
from ask.ui.spinner import Spinner
from ask.ui.textbox import PromptTextBox

TOOL_REJECTED_MESSAGE = (
    "The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, "
    "the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.")

def ToDoMessage(todos: dict[str, Any]) -> Component:
    return Box(margin={'top': 1})[
        Text(Colors.hex("To Do", Theme.GRAY)),
        Text(TOOLS[ToDoTool.name].render_response(todos, ''))
    ]

class Messages(dict[UUID, Message]):
    def __init__(self, parent_uuid: UUID, messages: dict[UUID, Message]) -> None:
        super().__init__(messages)
        self.parent_uuid = parent_uuid

    def __setitem__(self, key: UUID, value: Message) -> None:
        super().__setitem__(key, value)
        dirty.add(self.parent_uuid)

    def __delitem__(self, key: UUID) -> None:
        super().__delitem__(key)
        dirty.add(self.parent_uuid)

    def clear(self) -> None:
        super().clear()
        dirty.add(self.parent_uuid)

    def add(self, role: str, content: Content, uuid: UUID | None = None) -> UUID:
        message_uuid = uuid or uuid4()
        self[message_uuid] = Message(role=role, content=content)
        return message_uuid

    def set_contents(self, uuid: UUID, content: Content) -> None:
        self[uuid] = replace(self[uuid], content=content)


@dataclass
class App(Widget):
    __controller__: ClassVar = lambda _: AppController
    model: Model
    messages: dict[UUID, Message]
    tools: list[Tool]
    system_prompt: str

class AppController(Controller[App]):
    state = ['expanded', 'exiting', 'show_todos', 'pending', 'elapsed', 'approvals', 'autoapprovals', 'messages', 'model']
    expanded = False
    exiting = False
    show_todos = False
    pending = 0
    elapsed = 0.0
    approvals: dict[UUID, asyncio.Future] = {}
    autoapprovals: set[str] = set()

    def __init__(self, props: App) -> None:
        super().__init__(props)
        self.messages = Messages(self.uuid, self.props.messages)
        self.model = self.props.model
        self.config = Config()
        self.history = History()
        self.tasks: list[asyncio.Task] = []
        self.start_time = time.monotonic()
        self.query_time = 0.

    def exit(self) -> None:
        self.exiting = True
        asyncio.get_running_loop().call_later(0.1, sys.exit, 0)

    async def tick(self, interval: float) -> None:
        try:
            start_time = time.time()
            while True:
                self.elapsed = time.time() - start_time
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            self.elapsed = 0

    async def bash(self, command: str) -> None:
        ticker = asyncio.create_task(self.tick(1.0))
        bash_command = BashCommand(command=command)
        message_uuid = self.messages.add('user', bash_command)
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            status = ToolCallStatus.COMPLETED if process.returncode == 0 else ToolCallStatus.FAILED
            bash_command = replace(bash_command, stdout=stdout.decode().strip('\n'), stderr=stderr.decode().strip('\n'), status=status)
        except asyncio.CancelledError:
            bash_command = replace(bash_command, status=ToolCallStatus.CANCELLED)
        ticker.cancel()
        self.messages.set_contents(message_uuid, bash_command)

    async def python(self, command: str) -> None:
        ticker = asyncio.create_task(self.tick(1.0))
        python_command = PythonCommand(command=command)
        message_uuid = self.messages.add('user', python_command)
        try:
            nodes = PYTHON_SHELL.parse(command)
            output, exception = await PYTHON_SHELL.execute(nodes=nodes, timeout_seconds=10)
            status = ToolCallStatus.FAILED if exception else ToolCallStatus.COMPLETED
            python_command = replace(python_command, output=output, error=exception, status=status)
        except asyncio.CancelledError:
            python_command = replace(python_command, status=ToolCallStatus.CANCELLED)
        ticker.cancel()
        self.messages.set_contents(message_uuid, python_command)

    async def query(self) -> None:
        self.pending += 1
        text, contents = '', {}
        start_time = time.monotonic()
        messages = self.messages.copy()
        try:
            async for delta, content in query(self.model, list(messages.values()), self.props.tools, self.props.system_prompt):
                text = text + delta
                if content:
                    contents[uuid4()] = content
                text_content = {uuid4(): TextContent(text)} if text and not any(isinstance(c, TextContent) for c in contents.values()) else {}
                if text or contents:
                    new_messages = messages | {uuid: Message(role='assistant', content=c) for uuid, c in (contents | text_content).items()}
                    self.messages = Messages(self.uuid, new_messages)
        except asyncio.CancelledError:
            self.messages.add('user', Error("Request interrupted by user"))
        except Exception as e:
            self.messages.add('user', Error(str(e)))

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
            self.pending -= 1

    async def tool_call(self, request_uuid: UUID) -> None:
        request = self.messages[request_uuid].content
        assert isinstance(request, ToolRequest)
        try:
            tool = TOOLS[request.tool]
            args = tool.check(request.arguments)
            self.messages.set_contents(request_uuid, replace(request, processed_arguments=args))
            if tool.name in {BashTool.name, EditTool.name, MultiEditTool.name, PythonTool.name, WriteTool.name} - self.autoapprovals:
                self.approvals = self.approvals | {request_uuid: asyncio.get_running_loop().create_future()}
                try:
                    self.autoapprovals = self.autoapprovals | await self.approvals[request_uuid]
                finally:
                    self.approvals = {k:v for k,v in self.approvals.items() if k != request_uuid}
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
            self.messages.add('user', response)

    def handle_mount(self) -> None:
        messages = list(self.messages.values())
        if messages and messages[-1].role == 'user':
            match messages[-1].content:
                case TextContent(text): prompt = text
                case FilesCommand(command): prompt = command
                case _: prompt = ''
            if prompt:
                self.tasks.append(asyncio.create_task(self.query()))
                self.history.append(prompt)

    def handle_input(self, ch: str) -> None:
        if ch == '\x04':  # Ctrl+D
            self.exit()
        if ch == '\x03':  # Ctrl+C
            self.expanded = False
        elif ch == '\x12':  # Ctrl+R
            self.expanded = not self.expanded
        elif ch == '\x14':  # Ctrl+T
            self.show_todos = not self.show_todos
        elif ch == '\x1b[Z' and not self.approvals:  # Shift+Tab
            if EditApprovalController.autoapprovals & self.autoapprovals:
                self.autoapprovals = self.autoapprovals - EditApprovalController.autoapprovals
            else:
                self.autoapprovals = self.autoapprovals | EditApprovalController.autoapprovals
        elif ch == '\x1b' and not self.approvals:  # Escape key
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            self.tasks.clear()

    def handle_submit(self, value: str) -> bool:
        if any(not task.done() for task in self.tasks):
            return False

        self.history.append(value)
        value = value.rstrip()
        if value in ('/exit', '/quit', 'exit', 'quit'):
            self.exit()
        elif value == '/clear':
            self.messages.clear()
        elif value.startswith('/model'):
            model_name = value.removeprefix('/model').lstrip()
            if not model_name:
                model_list = '\n'.join(f"  {name} ({model.api.display_name})" for name, model in MODELS_BY_NAME.items())
                self.messages.add('user', SlashCommand(command='/model', output=f"Available models:\n{model_list}"))
            elif model_name not in MODELS_BY_NAME:
                self.messages.add('user', SlashCommand(command=value, error=f"Unknown model: {model_name}"))
            elif model_name != self.model.name:
                self.messages.add('user', SlashCommand(command=value, output=f"Switched from {self.model.name} to {model_name}"))
                self.model = MODELS_BY_NAME[model_name]
                # We have to remove all reasoning messages because they generally aren't compatible across models
                self.messages = Messages(self.uuid, {uuid: msg for uuid, msg in self.messages.items() if not isinstance(msg.content, Reasoning)})
        elif value == '/cost':
            output = get_usage_message(self.messages, self.query_time, time.monotonic() - self.start_time)
            self.messages.add('user', SlashCommand(command='/cost', output=output))
        elif value == '/init':
            self.messages.add('user', InitCommand(command='/init'))
            self.tasks.append(asyncio.create_task(self.query()))
        elif value.startswith('/edit'):
            if path := value.removeprefix('/edit').strip():
                editor = self.config['editor']
                os.system(f"{editor} {shlex.quote(path)}")
                hide_cursor()
            else:
                self.messages.add('user', SlashCommand(command='/edit', error='No file path supplied'))
        elif value.startswith('#'):
            agents_path = get_agents_md_path()
            content = agents_path.read_text() if agents_path else ''
            if content and not content.endswith('\n'):
                content += '\n'
            agents_path = agents_path or Path.cwd() / "AGENTS.md"
            agents_path.write_text(content + f"- {value.removeprefix('#').strip()}\n")
            self.messages.add('user', MemorizeCommand(command=value.removeprefix('#').strip()))
        elif value.startswith('!'):
            self.tasks.append(asyncio.create_task(self.bash(value.removeprefix('!'))))
        elif value.startswith('$'):
            self.tasks.append(asyncio.create_task(self.python(value.removeprefix('$'))))
        else:
            file_paths = [Path(m[1:]) for m in re.findall(r'@\S+', value) if Path(m[1:]).is_file()]  # get file attachments
            if file_paths:
                self.messages.add('user', FilesCommand(command=value, file_contents={fp: read_file(fp) for fp in file_paths}))
            else:
                self.messages.add('user', TextContent(value))
            self.tasks.append(asyncio.create_task(self.query()))
        return True

    def textbox(self) -> Component:
        if self.exiting:
            wall_time = time.monotonic() - self.start_time
            return Text(Colors.hex(get_usage_message(self.messages, self.query_time, wall_time), Theme.GRAY), margin={'top': 1})
        elif approval_uuid := next(iter(self.approvals.keys()), None):
            tool_call = self.messages[approval_uuid].content
            assert isinstance(tool_call, ToolRequest)
            return ApprovalDialog(
                tool_call=tool_call,
                future=self.approvals[approval_uuid])
        elif self.expanded:
            return Box(border={'top'})[
                Text(Colors.hex('  Showing detailed transcript · Ctrl+R to toggle', Theme.GRAY))
            ]
        else:
            return PromptTextBox(
                model=self.model,
                history=list(self.history),
                autoapprovals=self.autoapprovals,
                handle_submit=self.handle_submit,
                handle_exit=self.exit)

    def contents(self) -> list[Component | None]:
        tool_requests = {msg.content.call_id: msg.content for msg in self.messages.values() if isinstance(msg.content, ToolRequest)}
        tool_responses = {msg.content.call_id: msg.content for msg in self.messages.values() if isinstance(msg.content, ToolResponse)}
        if latest_todos := next((c.processed_arguments for c in reversed(tool_requests.values()) if c.tool == ToDoTool.name), None):
            if not any(todo['status'] in ['pending', 'in_progress'] for todo in latest_todos['todos']):
                latest_todos = None

        messages = []
        for uuid, msg in self.messages.items():
            match (msg.role, msg.content):
                case ('user', TextContent()):
                    messages.append(PromptMessage(text=msg.content))
                case ('user', Error()):
                    messages.append(ErrorMessage(error=msg.content))
                case ('user', BashCommand()):
                    messages.append(BashCommandMessage(command=msg.content, elapsed=self.elapsed, expanded=self.expanded))
                case ('user', MemorizeCommand()):
                    messages.append(MemorizeCommandMessage(command=msg.content))
                case ('user', PythonCommand()):
                    messages.append(PythonCommandMessage(command=msg.content, elapsed=self.elapsed, expanded=self.expanded))
                case ('user', SlashCommand()):
                    messages.append(SlashCommandMessage(command=msg.content))
                case ('assistant', TextContent()):
                    messages.append(ResponseMessage(text=msg.content))
                case ('assistant', ToolRequest()):
                    if msg.content.tool != ToDoTool.name:  # ToDo tool calls are handled specially
                        approved = uuid not in self.approvals
                        response = tool_responses.get(msg.content.call_id)
                        messages.append(ToolCallMessage(request=msg.content, response=response, approved=approved, expanded=self.expanded))
                case _:
                    pass

        return [
            Box()[*messages],
            Box()[
                Spinner(todos=latest_todos, expanded=self.show_todos)
                    if self.pending and not self.approvals else None,
                ToDoMessage(latest_todos)
                    if latest_todos and self.show_todos and not self.approvals else None,
            ],
            self.textbox(),
        ]
