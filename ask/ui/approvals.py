import asyncio

from ask.models import ToolRequest
from ask.prompts import get_relative_path
from ask.ui.core.components import Component, Box, Text
from ask.ui.core.markdown_ import highlight_code
from ask.ui.core.styles import Borders, Colors, Styles, Theme
from ask.ui.diff import Diff
from ask.tools import BashTool, EditTool, MultiEditTool, PythonTool, WriteTool


def Option(option: str, idx: int, active: bool, keybinding: str | None = None) -> Text:
    if active:
        return Text(Colors.hex(f'❯ {idx+1}. {option}' + (f' ({keybinding})' if keybinding else ''), Theme.BLUE))
    else:
        return Text(f'  {Colors.hex(f"{idx+1}.", Theme.GRAY)} {option}' + (f' ({Colors.hex(keybinding, Theme.GRAY)})' if keybinding else ''))

def OptionsList(options: dict[str, str | None], selected_idx: int) -> Box:
    return Box()[(Option(option, idx, idx == selected_idx, keybinding) for idx, (option, keybinding) in enumerate(options.items()))]

def Approval(tool_call: ToolRequest, future: asyncio.Future) -> Component:
    components = {
        BashTool.name: BashApproval,
        EditTool.name: EditApproval,
        MultiEditTool.name: EditApproval,
        PythonTool.name: PythonApproval,
        WriteTool.name: EditApproval}
    return components[tool_call.tool](tool_call, future)


class BaseApproval(Box):
    options: dict[str, str | None]
    initial_state = {'selected_idx': 0}

    def __init__(self, tool_call: ToolRequest, future: asyncio.Future) -> None:
        super().__init__(tool_call=tool_call, future=future)

    def handle_raw_input(self, ch: str) -> None:
        selected_idx = self.state['selected_idx']
        if ch == '\x03':  # Ctrl+C
            self.props['future'].cancel()
        elif ch in ('\x1b[A', '\x10'):  # Up arrow or Ctrl+P
            self.state['selected_idx'] = max(selected_idx - 1, 0)
        elif ch in ('\x1b[B', '\x0e'):  # Down arrow or Ctrl+N
            self.state['selected_idx'] = min(selected_idx + 1, len(self.options) - 1)
        elif ch == '\x1b':  # Escape key
            self.props['future'].cancel()
        elif ch == '\r':  # Enter key
            if selected_idx in (0, 1):  # 'Yes' or 'Yes, and always allow' option
                self.props['future'].set_result(True)
            else:  # 'No' option
                self.props['future'].cancel()


class BashApproval(BaseApproval):
    options = {
        'Yes': None,
        'Yes, allow all bash commands during this session': 'shift+tab',
        'No, and give instructions on what to do differently': 'esc'}

    def contents(self) -> list[Component | None]:
        description = self.props['tool_call'].arguments.get('description')
        return [
            Box(width=1.0, border_color=Colors.HEX(Theme.BLUE), border_style=Borders.ROUND, padding={'left': 1, 'right': 1}, margin={'top': 1})[
                Text(Styles.bold(Colors.hex("Bash command", Theme.BLUE)), margin={'bottom': 1}),
                Text(self.props['tool_call'].arguments['command'], margin={'left': 2}),
                Text(Colors.hex(description, Theme.GRAY), margin={'left': 2, 'bottom': 1}) if description else None,
                Text("Do you want to proceed?"),
                OptionsList(self.options, self.state['selected_idx']),
            ]
        ]


class PythonApproval(BaseApproval):
    options = {
        'Yes': None,
        'Yes, allow all Python commands during this session': 'shift+tab',
        'No, and give instructions on what to do differently': 'esc'}

    def contents(self) -> list[Component | None]:
        return [
            Box(width=1.0, border_color=Colors.HEX(Theme.BLUE), border_style=Borders.ROUND, padding={'left': 1, 'right': 1}, margin={'top': 1})[
                Text(Styles.bold(Colors.hex("Python code", Theme.BLUE)), margin={'bottom': 1}),
                Text(highlight_code(self.props['tool_call'].arguments['code'], language='python'), margin={'left': 2, 'bottom': 1}),
                Text("Do you want to proceed?"),
                OptionsList(self.options, self.state['selected_idx']),
            ]
        ]


class EditApproval(BaseApproval):
    options = {
        'Yes': None,
        'Yes, allow all edits during this session': 'shift+tab',
        'No, and give instructions on what to do differently': 'esc'}

    def contents(self) -> list[Component | None]:
        args = self.props['tool_call'].processed_arguments
        if not args['old_content']:
            title, operation = "Create file", "create"
        elif self.props['tool_call'].tool == 'Write':
            title, operation = "Overwrite file", "overwrite"
        else:
            title, operation = "Edit file", "make this edit to"

        return [
            Box(width=1.0, border_color=Colors.HEX(Theme.BLUE), border_style=Borders.ROUND, padding={'left': 1, 'right': 1}, margin={'top': 1})[
                Text(Styles.bold(Colors.hex(title, Theme.BLUE))),
                Box(width=1.0, border_color=Colors.HEX(Theme.DARK_GRAY), border_style=Borders.ROUND, padding={'left': 1, 'right': 1})[
                    Text(Styles.bold(get_relative_path(args['file_path'])), margin={'bottom': 1}),
                    Diff(diff=args['diff']) if args['old_content'] else Text(highlight_code(args['new_content'], file_path=str(args['file_path']))),
                ],
                Text(f"Do you want to {operation} {Styles.bold(get_relative_path(args['file_path']))}?"),
                OptionsList(self.options, self.state['selected_idx']),
            ]
        ]
