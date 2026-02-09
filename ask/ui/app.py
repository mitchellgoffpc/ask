from __future__ import annotations
import asyncio
import sys
import time
import traceback
from dataclasses import dataclass
from uuid import UUID

from ask.commands import BashCommand, PythonCommand, SlashCommand, get_usage, get_current_model
from ask.config import History
from ask.messages import Message, Text, ToolRequest, ToolResponse, Error
from ask.query import query_agent_with_commands
from ask.tools import BashTool, EditTool, MultiEditTool, PythonTool, ToDoTool, WriteTool
from ask.tree import MessageTree
from ask.ui.core import UI, ElementTree, Colors, Theme
from ask.ui.dialogs import EDIT_TOOLS, ApprovalDialog
from ask.ui.commands import ErrorMessage, PromptMessage, ResponseMessage, ToolCallMessage, BashCommandMessage, PythonCommandMessage, SlashCommandMessage
from ask.ui.spinner import Spinner
from ask.ui.textbox import PromptTextBox
from ask.ui.tools.todo import ToDos

@dataclass
class App(UI.Widget):
    messages: dict[UUID, Message]
    query: str

class AppController(UI.Controller[App]):
    state = ['expanded', 'exiting', 'show_todos', 'loading', 'elapsed', 'approvals', 'approved_tools', 'messages']
    expanded = False
    exiting = False
    show_todos = False
    loading = False
    elapsed = 0.0
    pending_approvals: dict[str, tuple[ToolRequest, asyncio.Future]] = {}
    approved_tools: set[str] = set()

    def __init__(self, props: App) -> None:
        super().__init__(props)
        self.messages = MessageTree(self.props.messages, onchange=lambda: self.set_dirty())
        self.head = list(self.props.messages.keys())[-1]
        self.tasks: list[asyncio.Task] = []

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

    async def approve(self, request: ToolRequest) -> bool:
        approval_tools = {BashTool.name, EditTool.name, MultiEditTool.name, PythonTool.name, WriteTool.name}
        if request.tool not in approval_tools or request.tool in self.approved_tools:
            return True
        future = asyncio.get_running_loop().create_future()
        self.pending_approvals = self.pending_approvals | {request.call_id: (request, future)}
        try:
            self.approved_tools = self.approved_tools | await future
            return True
        except asyncio.CancelledError:
            return False
        finally:
            self.pending_approvals = {k: v for k, v in self.pending_approvals.items() if k != request.call_id}

    async def query(self, query: str) -> None:
        self.loading = True
        History['queries'] = History.get('queries', []) + [query]
        ticker = asyncio.create_task(self.tick(0.1))

        try:
            async for head in query_agent_with_commands(self.messages, self.head, query, self.approve):
                self.head = head
        except asyncio.CancelledError:
            self.head = self.messages.add('user', self.head, Error("Request interrupted by user"))
        except Exception:
            self.head = self.messages.add('user', self.head, Error(traceback.format_exc()))

        self.loading = False
        ticker.cancel()

    def handle_mount(self, tree: ElementTree) -> None:
        super().handle_mount(tree)
        if self.props.query:
            self.tasks.append(asyncio.create_task(self.query(self.props.query)))

    def handle_input(self, ch: str) -> None:
        if ch == '\x03':  # Ctrl+C
            self.expanded = False
        elif ch == '\x12':  # Ctrl+R
            self.expanded = not self.expanded
        elif ch == '\x14':  # Ctrl+T
            self.show_todos = not self.show_todos
        elif ch == '\x1b[Z' and not self.pending_approvals:  # Shift+Tab
            if EDIT_TOOLS & self.approved_tools:
                self.approved_tools = self.approved_tools - EDIT_TOOLS
            else:
                self.approved_tools = self.approved_tools | EDIT_TOOLS
        elif ch == '\x1b' and not self.pending_approvals:  # Escape key
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            self.tasks.clear()

    def handle_submit(self, value: str) -> bool:
        if any(not task.done() for task in self.tasks):
            return False

        query = value.rstrip()
        if query in ('/exit', '/quit', 'exit', 'quit'):
            self.exit()
        else:
            self.tasks.append(asyncio.create_task(self.query(query)))
        return True

    def textbox(self) -> UI.Component:
        if self.exiting:
            return UI.Text(Colors.hex(get_usage(self.messages, self.head), Theme.GRAY), margin={'top': 1})
        elif tool_call_id := next(iter(self.pending_approvals.keys()), None):
            tool_call, future = self.pending_approvals[tool_call_id]
            return ApprovalDialog(tool_call=tool_call, future=future)
        elif self.expanded:
            return UI.Box(width=1.0, margin={'top': 1}, border=['top'])[
                UI.Text(Colors.hex('  Showing detailed transcript · Ctrl+R to toggle', Theme.GRAY))
            ]
        else:
            return PromptTextBox(
                model=get_current_model(self.messages.values(self.head)),
                approved_tools=self.approved_tools,
                handle_submit=self.handle_submit,
                handle_exit=self.exit)

    def contents(self) -> list[UI.Component | None]:
        tool_requests = {msg.content.call_id: msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, ToolRequest)}
        tool_responses = {msg.content.call_id: msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, ToolResponse)}
        if latest_todos := next((c.arguments for c in reversed(tool_requests.values()) if c.tool == ToDoTool.name), None):
            if not any(todo['status'] in ['pending', 'in_progress'] for todo in latest_todos['todos']):
                latest_todos = None

        messages = []
        for msg in self.messages.values(self.head):
            match (msg.role, msg.content):
                case ('user', Text()):
                    messages.append(PromptMessage(text=msg.content))
                case ('user', Error()):
                    messages.append(ErrorMessage(error=msg.content))
                case ('user', BashCommand()):
                    messages.append(BashCommandMessage(command=msg.content, elapsed=self.elapsed))
                case ('user', PythonCommand()):
                    messages.append(PythonCommandMessage(command=msg.content, elapsed=self.elapsed))
                case ('user', SlashCommand()):
                    messages.append(SlashCommandMessage(command=msg.content))
                case ('assistant', Text()):
                    messages.append(ResponseMessage(text=msg.content))
                case ('assistant', ToolRequest()):
                    if msg.content.tool != ToDoTool.name:  # ToDo tool calls are handled specially
                        response = tool_responses.get(msg.content.call_id)
                        messages.append(ToolCallMessage(request=msg.content, response=response, expanded=self.expanded))
                case _:
                    pass

        return [
            UI.Box()[*messages],
            UI.Box()[
                Spinner(todos=latest_todos, expanded=self.show_todos)
                    if self.loading and not self.pending_approvals else None,
                UI.Box(margin={'top': 1})[
                    UI.Text(Colors.hex("To Do", Theme.GRAY)),
                    ToDos(latest_todos, expanded=True)
                ] if latest_todos and self.show_todos and not self.pending_approvals else None,
            ],
            self.textbox(),
        ]
