from __future__ import annotations

import asyncio
import sys
import time
import traceback
from dataclasses import dataclass
from uuid import UUID

from ask.commands import BashCommand, PythonCommand, SlashCommand, get_current_model, get_usage
from ask.config import HISTORY_PATH, History
from ask.messages import Error, Message, Text, ToolRequest, ToolResponse, Usage
from ask.query import query_agent_with_commands
from ask.tools import BashTool, EditTool, MultiEditTool, PythonTool, ToDoTool, WriteTool
from ask.tree import MessageTree
from ask.ui.commands import BashCommandMessage, ErrorMessage, PromptMessage, PythonCommandMessage, ResponseMessage, SlashCommandMessage, ToolCallMessage
from ask.ui.core import UI, Colors, ElementTree, Theme
from ask.ui.dialogs import EDIT_TOOLS, ApprovalDialog
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
        self.messages = MessageTree(self.props.messages, onchange=self.handle_update_messages)
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

    def handle_update_messages(self) -> None:
        self.set_dirty()
        if root := self.messages.root:
            HISTORY_PATH.mkdir(parents=True, exist_ok=True)
            (HISTORY_PATH / f"{root}.json").write_text(self.messages.dump(self.head))

    def get_context_used(self) -> int:
        usage_messages = [msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, Usage)]
        if not usage_messages:
            return 0
        latest_usage = usage_messages[-1]
        return latest_usage.input + latest_usage.cache_write + latest_usage.cache_read + latest_usage.output

    def dialog(self) -> UI.Component | None:
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
            return None

    def textbox(self) -> list[UI.Component | None]:
        dialog = self.dialog()
        return [
            UI.Box(visible=dialog is None)[
                PromptTextBox(
                    model=get_current_model(self.messages.values(self.head)),
                    approved_tools=self.approved_tools,
                    context_used=self.get_context_used(),
                    handle_submit=self.handle_submit,
                    handle_exit=self.exit)
            ],
            dialog,
        ]

    def contents(self) -> list[UI.Component | None]:
        tool_requests = {msg.content.call_id: msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, ToolRequest)}
        tool_responses = {msg.content.call_id: msg.content for msg in self.messages.values(self.head) if isinstance(msg.content, ToolResponse)}
        latest_todos = next((c.arguments for c in reversed(tool_requests.values()) if c.tool == ToDoTool.name), None)
        if latest_todos and not any(todo['status'] in ['pending', 'in_progress'] for todo in latest_todos['todos']):
            latest_todos = None

        messages = []
        for msg in self.messages.values(self.head):
            match (msg.role, msg.content):
                case ('user', Text() as text):
                    messages.append(PromptMessage(text=text))
                case ('user', Error() as error):
                    messages.append(ErrorMessage(error=error))
                case ('user', BashCommand() as command):
                    messages.append(BashCommandMessage(command=command, elapsed=self.elapsed))
                case ('user', PythonCommand() as command):
                    messages.append(PythonCommandMessage(command=command, elapsed=self.elapsed))
                case ('user', SlashCommand() as command):
                    messages.append(SlashCommandMessage(command=command))
                case ('assistant', Text() as text):
                    messages.append(ResponseMessage(text=text))
                case ('assistant', ToolRequest() as request):
                    if request.tool != ToDoTool.name:  # ToDoTool calls are handled specially
                        response = tool_responses.get(request.call_id)
                        messages.append(ToolCallMessage(request=request, response=response, expanded=self.expanded))
                case _:
                    pass

        return [
            UI.Box()[*messages],
            UI.Box()[
                Spinner(todos=latest_todos, expanded=self.show_todos)
                    if self.loading and not self.pending_approvals else None,
                UI.Box(margin={'top': 1})[
                    UI.Text(Colors.hex("To Do", Theme.GRAY)),
                    ToDos(latest_todos, expanded=True),
                ] if latest_todos and self.show_todos and not self.pending_approvals else None,
            ],
            *self.textbox(),
        ]
