from __future__ import annotations
import asyncio
import re
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID, uuid4
from typing import ClassVar

from ask.commands import BashCommand, FilesCommand, InitCommand, PythonCommand, SlashCommand
from ask.commands import load_messages, save_messages, switch_model, get_usage
from ask.models import Model, Message, Text as TextContent, Reasoning, ToolRequest, ToolResponse, Error
from ask.query import query
from ask.tools import TOOLS, Tool, ToolCallStatus, BashTool, EditTool, MultiEditTool, PythonTool, ToDoTool, WriteTool
from ask.tools.read import read_file
from ask.tree import MessageTree
from ask.ui.core.components import Component, Controller, Box, Text, Widget
from ask.ui.core.styles import Colors, Theme
from ask.ui.dialogs import EDIT_TOOLS, ApprovalDialog
from ask.ui.commands import \
    ErrorMessage, PromptMessage, ResponseMessage, ToolCallMessage, BashCommandMessage, PythonCommandMessage, SlashCommandMessage
from ask.ui.config import Config, History
from ask.ui.spinner import Spinner
from ask.ui.textbox import PromptTextBox
from ask.ui.tools.todo import ToDos

TOOL_REJECTED_MESSAGE = (
    "The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, "
    "the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.")


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
        self.messages = MessageTree(self.uuid, self.props.messages)
        self.head = [None, *self.props.messages][-1]
        self.model = self.props.model
        self.config = Config()
        self.history = History()
        self.tasks: list[asyncio.Task] = []
        self.start_time = time.monotonic()
        self.query_time = 0.

    def exit(self) -> None:
        self.exiting = True
        asyncio.get_running_loop().call_later(0.1, sys.exit, 0)

    async def _tick(self, interval: float) -> None:
        try:
            start_time = time.time()
            while True:
                self.elapsed = time.time() - start_time
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            self.elapsed = 0

    async def tick(self, tasks: list[asyncio.Task], interval: float) -> None:
        ticker = asyncio.create_task(self._tick(interval))
        await asyncio.gather(*tasks)
        ticker.cancel()

    async def query(self) -> None:
        self.pending += 1
        original_head = self.head
        text_uuid: UUID = uuid4()
        text = ''
        start_time = time.monotonic()
        try:
            async for delta, content in query(self.model, self.messages.values(self.head), self.props.tools, self.props.system_prompt):
                text = text + delta
                if text_uuid not in self.messages.messages and (text or isinstance(content, TextContent)):  # create text content
                    self.head = self.messages.add('assistant', self.head, TextContent(''), uuid=text_uuid)
                if text:  # update streaming text content
                    self.messages.update(text_uuid, TextContent(text))
                if isinstance(content, TextContent):  # update final text content
                    self.messages.update(text_uuid, content)
                elif content:  # create non-text content
                    self.head = self.messages.add('assistant', self.head, content)
        except asyncio.CancelledError:
            self.head = self.messages.add('user', self.head, Error("Request interrupted by user"))
        except Exception as e:
            self.head = self.messages.add('user', self.head, Error(str(e)))

        contents = {k: v.content for k, v in self.messages.items(self.head)[len(self.messages.keys(original_head)):]}  # new contents only
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
            self.messages.update(request_uuid, replace(request, processed_arguments=args))
            if tool.name in {BashTool.name, EditTool.name, MultiEditTool.name, PythonTool.name, WriteTool.name} - self.autoapprovals:
                self.approvals = self.approvals | {request_uuid: asyncio.get_running_loop().create_future()}
                try:
                    self.autoapprovals = self.autoapprovals | await self.approvals[request_uuid]
                finally:
                    self.approvals = {k:v for k,v in self.approvals.items() if k != request_uuid}
            output = await tool.run(**args)
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=output, status=ToolCallStatus.COMPLETED)
        except asyncio.CancelledError:
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=TextContent(TOOL_REJECTED_MESSAGE), status=ToolCallStatus.CANCELLED)
            raise
        except Exception as e:
            response = ToolResponse(call_id=request.call_id, tool=request.tool, response=TextContent(str(e)), status=ToolCallStatus.FAILED)
        finally:
            self.head = self.messages.add('user', self.head, response)

    def handle_mount(self) -> None:
        messages = self.messages.values(self.head)
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
            if EDIT_TOOLS & self.autoapprovals:
                self.autoapprovals = self.autoapprovals - EDIT_TOOLS
            else:
                self.autoapprovals = self.autoapprovals | EDIT_TOOLS
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
            self.head = None
        elif value.startswith('/model'):
            self.head, self.model = switch_model(value.removeprefix('/model').lstrip(), self.model, self.messages, self.head)
        elif value == '/cost':
            output = get_usage(dict(self.messages.items(self.head)), self.query_time, time.monotonic() - self.start_time)
            self.head = self.messages.add('user', self.head, SlashCommand(command='/cost', output=output))
        elif value == '/init':
            self.head = self.messages.add('user', self.head, InitCommand(command='/init'))
            self.tasks.append(asyncio.create_task(self.query()))
        elif value.startswith('/save'):
            self.head = save_messages(value.removeprefix('/save').strip(), self.messages, self.head)
        elif value.startswith('/load'):
            self.head = load_messages(value.removeprefix('/load').strip(), self.messages, self.head)
        elif value.startswith('!'):
            self.head, tasks = BashCommand.create(value.removeprefix('!').strip(), self.messages, self.head)
            self.tasks.extend(tasks + [asyncio.create_task(self.tick(tasks, 1.0))])
        elif value.startswith('$'):
            self.head, tasks = PythonCommand.create(value.removeprefix('$').strip(), self.messages, self.head)
            self.tasks.extend(tasks + [asyncio.create_task(self.tick(tasks, 1.0))])
        else:
            file_paths = [Path(m[1:]) for m in re.findall(r'@\S+', value) if Path(m[1:]).is_file()]  # get file attachments
            if file_paths:
                self.head = self.messages.add('user', self.head, FilesCommand(command=value, file_contents={fp: read_file(fp) for fp in file_paths}))
            else:
                self.head = self.messages.add('user', self.head, TextContent(value))
            self.tasks.append(asyncio.create_task(self.query()))
        return True

    def textbox(self) -> Component:
        if self.exiting:
            wall_time = time.monotonic() - self.start_time
            return Text(Colors.hex(get_usage(dict(self.messages.items(self.head)), self.query_time, wall_time), Theme.GRAY), margin={'top': 1})
        elif approval_uuid := next(iter(self.approvals.keys()), None):
            tool_call = self.messages[approval_uuid].content
            assert isinstance(tool_call, ToolRequest)
            return ApprovalDialog(
                tool_call=tool_call,
                future=self.approvals[approval_uuid])
        elif self.expanded:
            return Box(width=1.0, margin={'top': 1}, border=['top'])[
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
        tool_requests = {msg.content.call_id: msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, ToolRequest)}
        tool_responses = {msg.content.call_id: msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, ToolResponse)}
        if latest_todos := next((c.processed_arguments for c in reversed(tool_requests.values()) if c.tool == ToDoTool.name), None):
            if not any(todo['status'] in ['pending', 'in_progress'] for todo in latest_todos['todos']):
                latest_todos = None

        messages = []
        for msg in self.messages.values(self.head):
            match (msg.role, msg.content):
                case ('user', TextContent()):
                    messages.append(PromptMessage(text=msg.content))
                case ('user', Error()):
                    messages.append(ErrorMessage(error=msg.content))
                case ('user', BashCommand()):
                    messages.append(BashCommandMessage(command=msg.content, elapsed=self.elapsed))
                case ('user', PythonCommand()):
                    messages.append(PythonCommandMessage(command=msg.content, elapsed=self.elapsed))
                case ('user', SlashCommand()):
                    messages.append(SlashCommandMessage(command=msg.content))
                case ('assistant', TextContent()):
                    messages.append(ResponseMessage(text=msg.content))
                case ('assistant', ToolRequest()):
                    if msg.content.tool != ToDoTool.name:  # ToDo tool calls are handled specially
                        response = tool_responses.get(msg.content.call_id)
                        messages.append(ToolCallMessage(request=msg.content, response=response, expanded=self.expanded))
                case _:
                    pass

        return [
            Box()[*messages],
            Box()[
                Spinner(todos=latest_todos, expanded=self.show_todos)
                    if self.pending and not self.approvals else None,
                Box(margin={'top': 1})[
                    Text(Colors.hex("To Do", Theme.GRAY)),
                    ToDos(latest_todos, expanded=True)
                ] if latest_todos and self.show_todos and not self.approvals else None,
            ],
            self.textbox(),
        ]
