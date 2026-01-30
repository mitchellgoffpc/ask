import asyncio
from functools import partial
from dataclasses import dataclass

from ask.messages import ToolRequest
from ask.tools import BashTool, EditTool, MultiEditTool, PythonTool, WriteTool
from ask.ui.core import UI, Colors, Theme

EDIT_TOOLS = {EditTool.name, MultiEditTool.name, WriteTool.name}

def get_formatted_options(command_type: str) -> dict[str, str | None]:
    return {
        'Yes': None,
        f'Yes, allow all {command_type} during this session': 'shift+tab',
        'No, and give instructions on what to do differently': 'esc'}

def Option(option: str, idx: int, active: bool, keybinding: str | None = None) -> UI.Text:
    if active:
        return UI.Text(Colors.hex(f'❯ {idx+1}. {option}' + (f' ({keybinding})' if keybinding else ''), Theme.BLUE))
    else:
        return UI.Text(f'  {Colors.hex(f"{idx+1}.", Theme.GRAY)} {option}' + (f' ({Colors.hex(keybinding, Theme.GRAY)})' if keybinding else ''))

def OptionsList(options: dict[str, str | None], selected_idx: int) -> UI.Box:
    return UI.Box()[(Option(option, idx, idx == selected_idx, keybinding) for idx, (option, keybinding) in enumerate(options.items()))]

def ApprovalDialog(tool_call: ToolRequest, future: asyncio.Future) -> UI.Component:

    components = {
        BashTool.name: partial(SelectionDialog, approved_tools={BashTool.name}, options=get_formatted_options('bash commands')),
        EditTool.name: partial(SelectionDialog, approved_tools=EDIT_TOOLS, options=get_formatted_options('edits')),
        MultiEditTool.name: partial(SelectionDialog, approved_tools=EDIT_TOOLS, options=get_formatted_options('edits')),
        PythonTool.name: partial(SelectionDialog, approved_tools={PythonTool.name}, options=get_formatted_options('Python commands')),
        WriteTool.name: partial(SelectionDialog, approved_tools=EDIT_TOOLS, options=get_formatted_options('edits'))}
    return UI.Box(margin={'top': 1})[
        components[tool_call.tool](tool_call=tool_call, future=future)
    ]


@dataclass
class SelectionDialog(UI.Widget):
    tool_call: ToolRequest
    future: asyncio.Future
    approved_tools: set[str]
    options: dict[str, str | None]

class SelectionDialogController(UI.Controller[SelectionDialog]):
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
            self.props.future.set_result(self.props.approved_tools)
        elif ch == '\r':  # Enter key
            if selected_idx == 0:  # 'Yes' option
                self.props.future.set_result(set())
            elif selected_idx == 1:  # 'Yes, and always allow' option
                self.props.future.set_result(self.props.approved_tools)
            else:  # 'No' option
                self.props.future.cancel()

    def contents(self) -> list[UI.Component | None]:
        return [
            UI.Text("Do you want to proceed?"),
            OptionsList(self.props.options, self.selected_idx),
        ]
