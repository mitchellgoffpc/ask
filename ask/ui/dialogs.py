import asyncio
from functools import partial
from dataclasses import dataclass
from typing import ClassVar

from ask.models import ToolRequest
from ask.tools import BashTool, EditTool, MultiEditTool, PythonTool, WriteTool
from ask.ui.core.components import Box, Component, Controller, Text, Widget
from ask.ui.core.styles import Colors, Theme

EDIT_TOOLS = {EditTool.name, MultiEditTool.name, WriteTool.name}

def get_formatted_options(command_type: str) -> dict[str, str | None]:
    return {
        'Yes': None,
        f'Yes, allow all {command_type} during this session': 'shift+tab',
        'No, and give instructions on what to do differently': 'esc'}

def Option(option: str, idx: int, active: bool, keybinding: str | None = None) -> Text:
    if active:
        return Text(Colors.hex(f'❯ {idx+1}. {option}' + (f' ({keybinding})' if keybinding else ''), Theme.BLUE))
    else:
        return Text(f'  {Colors.hex(f"{idx+1}.", Theme.GRAY)} {option}' + (f' ({Colors.hex(keybinding, Theme.GRAY)})' if keybinding else ''))

def OptionsList(options: dict[str, str | None], selected_idx: int) -> Box:
    return Box()[(Option(option, idx, idx == selected_idx, keybinding) for idx, (option, keybinding) in enumerate(options.items()))]

def ApprovalDialog(tool_call: ToolRequest, future: asyncio.Future) -> Component:

    components = {
        BashTool.name: partial(SelectionDialog, autoapprovals={BashTool.name}, options=get_formatted_options('bash commands')),
        EditTool.name: partial(SelectionDialog, autoapprovals=EDIT_TOOLS, options=get_formatted_options('edits')),
        MultiEditTool.name: partial(SelectionDialog, autoapprovals=EDIT_TOOLS, options=get_formatted_options('edits')),
        PythonTool.name: partial(SelectionDialog, autoapprovals={PythonTool.name}, options=get_formatted_options('Python commands')),
        WriteTool.name: partial(SelectionDialog, autoapprovals=EDIT_TOOLS, options=get_formatted_options('edits'))}
    return Box(margin={'top': 1})[
        components[tool_call.tool](tool_call=tool_call, future=future)
    ]


@dataclass
class SelectionDialog(Widget):
    __controller__: ClassVar = lambda _: SelectionDialogController
    tool_call: ToolRequest
    future: asyncio.Future
    autoapprovals: set[str]
    options: dict[str, str | None]

class SelectionDialogController(Controller[SelectionDialog]):
    state = ['selected_idx']
    selected_idx: int = 0

    def handle_input(self, ch: str) -> None:
        selected_idx = self.selected_idx
        if ch == '\x03':  # Ctrl+C
            self.props.future.cancel()
        elif ch in ('\x1b[A', '\x10'):  # Up arrow or Ctrl+P
            self.selected_idx = max(selected_idx - 1, 0)
        elif ch in ('\x1b[B', '\x0e'):  # Down arrow or Ctrl+N
            self.selected_idx = min(selected_idx + 1, len(self.props.options) - 1)
        elif ch == '\x1b':  # Escape key
            self.props.future.cancel()
        elif ch == '\x1b[Z':  # Shift+Tab
            self.props.future.set_result(self.props.autoapprovals)
        elif ch == '\r':  # Enter key
            if selected_idx == 0:  # 'Yes' option
                self.props.future.set_result(set())
            elif selected_idx == 1:  # 'Yes, and always allow' option
                self.props.future.set_result(self.props.autoapprovals)
            else:  # 'No' option
                self.props.future.cancel()

    def contents(self) -> list[Component | None]:
        return [
            Text("Do you want to proceed?"),
            OptionsList(self.props.options, self.selected_idx),
        ]
