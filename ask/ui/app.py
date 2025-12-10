from __future__ import annotations
import asyncio
import json
import os
import re
import shlex
import sys
import time
from dataclasses import dataclass, replace
from itertools import pairwise
from pathlib import Path
from uuid import UUID, uuid4
from typing import Any, ClassVar, get_args

from ask.models import MODELS_BY_NAME, Model, Message, Role, Content, Text as TextContent, Reasoning, ToolRequest, ToolResponse, Error
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

class MessageEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return {'__type__': 'Path', 'path': str(obj)}
        elif isinstance(obj, UUID):
            return {'__type__': 'UUID', 'uuid': str(obj)}
        elif isinstance(obj, Model):
            return {'__type__': 'Model', 'name': obj.name}
        elif isinstance(obj, Content):
            data = obj.__dict__.copy()
            data['__type__'] = obj.__class__.__name__
            return data
        return super().default(obj)

def message_decoder(obj):
    if isinstance(obj, dict) and obj.get('__type__') == 'Path':
        return Path(obj['path'])
    elif isinstance(obj, dict) and obj.get('__type__') == 'UUID':
        return UUID(obj['uuid'])
    elif isinstance(obj, dict) and obj.get('__type__') == 'Model':
        return MODELS_BY_NAME[obj['name']]
    elif isinstance(obj, dict) and obj.get('__type__') in [cls.__name__ for cls in get_args(Content)]:
        type_name = obj.pop('__type__')
        content_types = {cls.__name__: cls for cls in get_args(Content)}
        return content_types[type_name](**obj)
    return obj

def ToDoMessage(todos: dict[str, Any]) -> Component:
    return Box(margin={'top': 1})[
        Text(Colors.hex("To Do", Theme.GRAY)),
        Text(TOOLS[ToDoTool.name].render_response(todos, ''))
    ]

class MessageTree:
    def __init__(self, parent_uuid: UUID, messages: dict[UUID, Message]) -> None:
        self.parent_uuid = parent_uuid
        self.messages = messages.copy()
        self.parents = {child: parent for parent, child in pairwise((None, *messages.keys()))}

    def __getitem__(self, key: UUID) -> Message:
        return self.messages[key]

    def __setitem__(self, key: UUID, value: Message) -> None:
        self.messages[key] = value
        dirty.add(self.parent_uuid)

    def clear(self) -> None:
        self.messages.clear()
        self.parents.clear()
        dirty.add(self.parent_uuid)

    def keys(self, head: UUID | None) -> list[UUID]:
        keys = []
        while head is not None:
            keys.append(head)
            head = self.parents[head]
        return keys[::-1]

    def values(self, head: UUID | None) -> list[Message]:
        return [self.messages[k] for k in self.keys(head)]

    def items(self, head: UUID | None) -> list[tuple[UUID, Message]]:
        return list(zip(self.keys(head), self.values(head), strict=True))

    def add(self, role: Role, head: UUID | None, content: Content, uuid: UUID | None = None) -> UUID:
        message_uuid = uuid or uuid4()
        self[message_uuid] = Message(role=role, content=content)
        self.parents[message_uuid] = head
        return message_uuid

    def update(self, uuid: UUID, content: Content) -> None:
        self[uuid] = replace(self[uuid], content=content)

    def dump(self) -> list[dict[str, Any]]:
        return [{'uuid': uuid, 'parent': self.parents[uuid], 'role': msg.role, 'content': msg.content} for uuid, msg in self.messages.items()]

    def load(self, data: list[dict[str, Any]]) -> None:
        self.clear()
        for message in data:
            self[message['uuid']] = Message(role=message['role'], content=message['content'])
            self.parents[message['uuid']] = message['parent']


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
        self.head = message_uuid = self.messages.add('user', self.head, bash_command)
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            status = ToolCallStatus.COMPLETED if process.returncode == 0 else ToolCallStatus.FAILED
            bash_command = replace(bash_command, stdout=stdout.decode().strip('\n'), stderr=stderr.decode().strip('\n'), status=status)
        except asyncio.CancelledError:
            bash_command = replace(bash_command, status=ToolCallStatus.CANCELLED)
        ticker.cancel()
        self.messages.update(message_uuid, bash_command)

    async def python(self, command: str) -> None:
        ticker = asyncio.create_task(self.tick(1.0))
        python_command = PythonCommand(command=command)
        self.head = message_uuid = self.messages.add('user', self.head, python_command)
        try:
            nodes = PYTHON_SHELL.parse(command)
            output, exception = await PYTHON_SHELL.execute(nodes=nodes, timeout_seconds=10)
            status = ToolCallStatus.FAILED if exception else ToolCallStatus.COMPLETED
            python_command = replace(python_command, output=output, error=exception, status=status)
        except asyncio.CancelledError:
            python_command = replace(python_command, status=ToolCallStatus.CANCELLED)
        ticker.cancel()
        self.messages.update(message_uuid, python_command)

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
            self.head = None
        elif value.startswith('/model'):
            model_name = value.removeprefix('/model').lstrip()
            if not model_name:
                model_list = '\n'.join(f"  {name} ({model.api.display_name})" for name, model in MODELS_BY_NAME.items())
                self.head = self.messages.add('user', self.head, SlashCommand(command='/model', output=f"Available models:\n{model_list}"))
            elif model_name not in MODELS_BY_NAME:
                self.head = self.messages.add('user', self.head, SlashCommand(command=value, error=f"Unknown model: {model_name}"))
            elif model_name != self.model.name:
                self.head = self.messages.add('user', self.head, SlashCommand(command=value, output=f"Switched from {self.model.name} to {model_name}"))
                self.model = MODELS_BY_NAME[model_name]
        elif value == '/cost':
            output = get_usage_message(dict(self.messages.items(self.head)), self.query_time, time.monotonic() - self.start_time)
            self.head = self.messages.add('user', self.head, SlashCommand(command='/cost', output=output))
        elif value == '/init':
            self.head = self.messages.add('user', self.head, InitCommand(command='/init'))
            self.tasks.append(asyncio.create_task(self.query()))
        elif value.startswith('/edit'):
            if path := value.removeprefix('/edit').strip():
                editor = self.config['editor']
                os.system(f"{editor} {shlex.quote(path)}")
                hide_cursor()
            else:
                self.head = self.messages.add('user', self.head, SlashCommand(command='/edit', error='No file path supplied'))
        elif value.startswith('/save'):
            if path := value.removeprefix('/save').strip():
                try:
                    Path(path).write_text(json.dumps({'head': self.head, 'messages': self.messages.dump()}, indent=2, cls=MessageEncoder))
                    self.head = self.messages.add('user', self.head, SlashCommand(command=value, output=f'Saved messages to {path}'))
                except Exception as e:
                    self.head = self.messages.add('user', self.head, SlashCommand(command=value, error=str(e)))
            else:
                self.head = self.messages.add('user', self.head, SlashCommand(command='/save', error='No file path supplied'))
        elif value.startswith('/load'):
            if path := value.removeprefix('/load').strip():
                try:
                    data = json.loads(Path(path).read_text(), object_hook=message_decoder)
                    self.head = data['head']
                    self.messages.load(data['messages'])
                except Exception as e:
                    self.head = self.messages.add('user', self.head, SlashCommand(command=value, error=str(e)))
            else:
                self.head = self.messages.add('user', self.head, SlashCommand(command='/load', error='No file path supplied'))
        elif value.startswith('#'):
            agents_path = get_agents_md_path()
            content = agents_path.read_text() if agents_path else ''
            if content and not content.endswith('\n'):
                content += '\n'
            agents_path = agents_path or Path.cwd() / "AGENTS.md"
            agents_path.write_text(content + f"- {value.removeprefix('#').strip()}\n")
            self.head = self.messages.add('user', self.head, MemorizeCommand(command=value.removeprefix('#').strip()))
        elif value.startswith('!'):
            self.tasks.append(asyncio.create_task(self.bash(value.removeprefix('!'))))
        elif value.startswith('$'):
            self.tasks.append(asyncio.create_task(self.python(value.removeprefix('$'))))
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
            return Text(Colors.hex(get_usage_message(dict(self.messages.items(self.head)), self.query_time, wall_time), Theme.GRAY), margin={'top': 1})
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
        tool_requests = {msg.content.call_id: msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, ToolRequest)}
        tool_responses = {msg.content.call_id: msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, ToolResponse)}
        if latest_todos := next((c.processed_arguments for c in reversed(tool_requests.values()) if c.tool == ToDoTool.name), None):
            if not any(todo['status'] in ['pending', 'in_progress'] for todo in latest_todos['todos']):
                latest_todos = None

        messages = []
        for uuid, msg in self.messages.items(self.head):
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
