from ask.tools import TOOLS, Tool
from ask.models import Status
from ask.ui.components import Component, Box, Text
from ask.ui.markdown_ import render_markdown
from ask.ui.styles import Flex, Colors, Styles, Theme

NUM_PREVIEW_LINES = 5

def get_shell_output(result: str, status: Status, elapsed: float, expanded: bool) -> str:
    if status is Status.PENDING:
        return Colors.hex("Running…" + (f" ({int(elapsed)}s)" if elapsed >= 1 else ""), Theme.GRAY)
    elif status is Status.CANCELLED:
        return Colors.ansi("Interrupted by user", Colors.RED)
    elif not result:
        return Colors.hex("(No content)", Theme.GRAY)
    elif expanded:
        return result
    else:
        lines = result.rstrip('\n').split('\n')
        expand_text = Colors.hex(f"… +{len(lines) - NUM_PREVIEW_LINES} lines (ctrl+r to expand)", Theme.GRAY)
        return '\n'.join(lines[:NUM_PREVIEW_LINES]) + (f'\n{expand_text}' if len(lines) > NUM_PREVIEW_LINES else '')

def get_tool_result(tool: Tool, result: str, expanded: bool) -> str:
    if expanded:
        return tool.render_response(result)
    else:
        return f"{tool.render_short_response(result)} {Colors.hex('(ctrl+r to expand)', Theme.GRAY)}"


# Components

def Prompt(text: str, error: str | None) -> Component:
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("> ", Theme.GRAY)),
            Text(Colors.hex(text, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("  ⎿  ", Theme.GRAY)),
            Text(Colors.ansi(error, Colors.RED))
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
            Text(Colors.ansi(error, Colors.RED))
        ] if status is Status.COMPLETED and error else None,
    ]

def TextResponse(text: str) -> Component:
    return Box(flex=Flex.HORIZONTAL, margin={'top': 1})[
        Text("● "),
        Text(render_markdown(text))
    ]

def ToolCall(tool: str, args: dict[str, str], result: str | None, expanded: bool = True) -> Component:
    args_str = TOOLS[tool].render_args(args)

    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.ansi("● ", Colors.GREEN) if result is not None else "● "),
            Text(Styles.bold(tool) + (f"({args_str})" if args_str else ''))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(get_tool_result(TOOLS[tool], result, expanded))
        ] if result is not None else None,
    ]
