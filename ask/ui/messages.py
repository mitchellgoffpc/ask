from ask.tools import TOOLS, Tool
from ask.models import Status
from ask.ui.components import Component, Box, Text
from ask.ui.markdown_ import render_markdown
from ask.ui.styles import Flex, Colors, Styles, Theme

NUM_PREVIEW_LINES = 5
STATUS_COLORS = {
    Status.PENDING: Theme.GRAY,
    Status.COMPLETED: Theme.GREEN,
    Status.CANCELLED: Theme.RED,
    Status.FAILED: Theme.RED,
}

def get_shell_output(result: str, status: Status, elapsed: float, expanded: bool) -> str:
    if status is Status.PENDING:
        return Colors.hex("Running…" + (f" ({int(elapsed)}s)" if elapsed >= 1 else ""), Theme.GRAY)
    elif status is Status.CANCELLED:
        return Colors.hex("Interrupted by user", Theme.RED)
    elif status is Status.FAILED:
        return Colors.hex(f"Error: {result}", Theme.RED)
    elif status is Status.COMPLETED:
        if not result:
            return Colors.hex("(No content)", Theme.GRAY)
        elif expanded:
            return result
        else:
            lines = result.rstrip('\n').split('\n')
            expand_text = Colors.hex(f"… +{len(lines) - NUM_PREVIEW_LINES} lines (ctrl+r to expand)", Theme.GRAY)
            return '\n'.join(lines[:NUM_PREVIEW_LINES]) + (f'\n{expand_text}' if len(lines) > NUM_PREVIEW_LINES else '')

def get_tool_result(tool: Tool, result: str, status: Status, expanded: bool) -> str:
    if status is Status.PENDING:
        return Colors.hex("Running…", Theme.GRAY)
    elif status is Status.CANCELLED:
        return Colors.hex("Tool call cancelled by user", Theme.RED)
    elif status is Status.FAILED:
        return Colors.hex(tool.render_error(result), Theme.RED)
    elif status is Status.COMPLETED:
        if not result:
            return Colors.hex("(No content)", Theme.GRAY)
        elif expanded:
            return tool.render_response(result)
        else:
            return tool.render_short_response(result)


# Components

def Prompt(text: str, error: str | None) -> Component:
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("> ", Theme.GRAY)),
            Text(Colors.hex(text, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("  ⎿  ", Theme.GRAY)),
            Text(Colors.hex(error, Theme.RED))
        ] if error else None,
    ]

def ShellCall(command: str, output: str, error: str, status: Status, elapsed: float, expanded: bool = True) -> Component:
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("! ", Theme.PINK)),
            Text(Colors.hex(command, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(get_shell_output(output, status, elapsed, expanded))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(Colors.hex(error, Theme.RED))
        ] if status is Status.COMPLETED and error else None,
    ]

def TextResponse(text: str) -> Component:
    return Box(flex=Flex.HORIZONTAL, margin={'top': 1})[
        Text("● "),
        Text(render_markdown(text))
    ]

def ToolCall(tool: str, args: dict[str, str], result: str, status: Status, expanded: bool = True) -> Component:
    args_str = TOOLS[tool].render_args(args)

    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("● ", STATUS_COLORS[status])),
            Text(Styles.bold(tool) + (f"({args_str})" if args_str else ''))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(get_tool_result(TOOLS[tool], result, status, expanded))
        ],
    ]
