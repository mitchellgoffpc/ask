from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import ClassVar, get_args

from ask.models import ToolRequest
from ask.prompts import get_relative_path
from ask.tools import BashTool, EditTool, MultiEditTool, PythonTool, WriteTool
from ask.ui.core.components import Box, Component, Controller, Side, Text, Widget
from ask.ui.core.diff import Diff
from ask.ui.core.markdown_ import highlight_code
from ask.ui.core.styles import Colors, Styles, Theme

def Option(option: str, idx: int, active: bool, keybinding: str | None = None) -> Text:
    if active:
        return Text(Colors.hex(f'❯ {idx+1}. {option}' + (f' ({keybinding})' if keybinding else ''), Theme.BLUE))
    else:
        return Text(f'  {Colors.hex(f"{idx+1}.", Theme.GRAY)} {option}' + (f' ({Colors.hex(keybinding, Theme.GRAY)})' if keybinding else ''))

def OptionsList(options: dict[str, str | None], selected_idx: int) -> Box:
    return Box()[(Option(option, idx, idx == selected_idx, keybinding) for idx, (option, keybinding) in enumerate(options.items()))]

def ApprovalDialog(tool_call: ToolRequest, future: asyncio.Future) -> SelectionDialog:
    components = {
        BashTool.name: BashApproval,
        EditTool.name: EditApproval,
        MultiEditTool.name: EditApproval,
        PythonTool.name: PythonApproval,
        WriteTool.name: EditApproval}
    return components[tool_call.tool](tool_call=tool_call, future=future)


@dataclass
class SelectionDialog(Widget):
    tool_call: ToolRequest
    future: asyncio.Future

class SelectionDialogController(Controller[SelectionDialog]):
    state = ['selected_idx']
    options: dict[str, str | None]
    autoapprovals: set[str] = set()
    selected_idx: int = 0

    def handle_input(self, ch: str) -> None:
        selected_idx = self.selected_idx
        if ch == '\x03':  # Ctrl+C
            self.props.future.cancel()
        elif ch in ('\x1b[A', '\x10'):  # Up arrow or Ctrl+P
            self.selected_idx = max(selected_idx - 1, 0)
        elif ch in ('\x1b[B', '\x0e'):  # Down arrow or Ctrl+N
            self.selected_idx = min(selected_idx + 1, len(self.options) - 1)
        elif ch == '\x1b':  # Escape key
            self.props.future.cancel()
        elif ch == '\x1b[Z':  # Shift+Tab
            self.props.future.set_result(self.autoapprovals)
        elif ch == '\r':  # Enter key
            if selected_idx == 0:  # 'Yes' option
                self.props.future.set_result(set())
            elif selected_idx == 1:  # 'Yes, and always allow' option
                self.props.future.set_result(self.autoapprovals)
            else:  # 'No' option
                self.props.future.cancel()


# Approval dialogs

@dataclass
class BashApproval(SelectionDialog):
    __controller__: ClassVar = lambda _: BashApprovalController

class BashApprovalController(SelectionDialogController):
    autoapprovals = {BashTool.name}
    options = {
        'Yes': None,
        'Yes, allow all bash commands during this session': 'shift+tab',
        'No, and give instructions on what to do differently': 'esc'}

    def contents(self) -> list[Component | None]:
        description = self.props.tool_call.arguments.get('description')
        return [
            Box(width=1.0, padding={'left': 1, 'right': 1}, margin={'top': 1}, border=get_args(Side), border_color=Colors.HEX(Theme.BLUE))[
                Text(Styles.bold(Colors.hex("Bash command", Theme.BLUE)), margin={'bottom': 1}),
                Text(self.props.tool_call.arguments['command'], margin={'left': 2}),
                Text(Colors.hex(description, Theme.GRAY), margin={'left': 2, 'bottom': 1}) if description else None,
                Text("Do you want to proceed?"),
                OptionsList(self.options, self.selected_idx),
            ]
        ]


@dataclass
class PythonApproval(SelectionDialog):
    __controller__: ClassVar = lambda _: PythonApprovalController

class PythonApprovalController(SelectionDialogController):
    autoapprovals = {PythonTool.name}
    options = {
        'Yes': None,
        'Yes, allow all Python commands during this session': 'shift+tab',
        'No, and give instructions on what to do differently': 'esc'}

    def contents(self) -> list[Component | None]:
        return [
            Box(width=1.0, padding={'left': 1, 'right': 1}, margin={'top': 1}, border=get_args(Side), border_color=Colors.HEX(Theme.BLUE))[
                Text(Styles.bold(Colors.hex("Python code", Theme.BLUE)), margin={'bottom': 1}),
                Text(highlight_code(self.props.tool_call.arguments['code'], language='python'), margin={'left': 2, 'bottom': 1}),
                Text("Do you want to proceed?"),
                OptionsList(self.options, self.selected_idx),
            ]
        ]


@dataclass
class EditApproval(SelectionDialog):
    __controller__: ClassVar = lambda _: EditApprovalController

class EditApprovalController(SelectionDialogController):
    autoapprovals = {EditTool.name, MultiEditTool.name, WriteTool.name}
    options = {
        'Yes': None,
        'Yes, allow all edits during this session': 'shift+tab',
        'No, and give instructions on what to do differently': 'esc'}

    def contents(self) -> list[Component | None]:
        args = self.props.tool_call.processed_arguments
        assert args is not None
        if not args['old_content']:
            title, operation = "Create file", "create"
        elif self.props.tool_call.tool == 'Write':
            title, operation = "Overwrite file", "overwrite"
        else:
            title, operation = "Edit file", "make this edit to"

        return [
            Box(width=1.0, padding={'left': 1, 'right': 1}, margin={'top': 1}, border=get_args(Side), border_color=Colors.HEX(Theme.BLUE))[
                Text(Styles.bold(Colors.hex(title, Theme.BLUE))),
                Box(width=1.0, padding={'left': 1, 'right': 1}, border=get_args(Side), border_color=Colors.HEX(Theme.DARK_GRAY))[
                    Text(Styles.bold(get_relative_path(args['file_path'])), margin={'bottom': 1}),
                    Diff(diff=args['diff']) if args['old_content'] else Text(highlight_code(args['new_content'], file_path=str(args['file_path']))),
                ],
                Text(f"Do you want to {operation} {Styles.bold(get_relative_path(args['file_path']))}?"),
                OptionsList(self.options, self.selected_idx),
            ]
        ]
