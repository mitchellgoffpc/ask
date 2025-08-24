from typing import Any

from ask.models import Text as TextContent, TextPrompt, ToolRequest, ToolResponse, ShellCommand, Status
from ask.prompts import get_relative_path
from ask.tools import TOOLS, Tool
from ask.ui.components import Component, Box, Text
from ask.ui.diff import Diff
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

def get_tool_result(tool: Tool, args: dict[str, Any], result: str, status: Status, expanded: bool) -> str:
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
            return tool.render_response(args, result)
        else:
            return tool.render_short_response(args, result)

def get_edit_result(args: dict[str, Any], result: str, status: Status, expanded: bool) -> Component:
    if status is Status.PENDING:
        return Text(Colors.hex("Waiting…", Theme.GRAY))
    elif status is Status.FAILED:
        return Text(Colors.hex(result, Theme.RED))
    elif status is Status.CANCELLED:
        operation = 'update' if args['old_content'] else 'write'
        return Box()[
            Text(Colors.hex(f"User rejected {operation} to {Styles.bold(get_relative_path(args['file_path']))}", Theme.RED)),
            Diff(diff=args['diff'], rejected=True)
        ]
    elif status is Status.COMPLETED and not args['old_content']:
        return Text(get_tool_result(TOOLS['Write'], args, result, status, expanded))
    elif status is Status.COMPLETED:
        num_additions = sum(1 for line in args['diff'] if line.startswith('+') and not line.startswith('+++'))
        num_deletions = sum(1 for line in args['diff'] if line.startswith('-') and not line.startswith('---'))
        addition_text = f"{Styles.bold(str(num_additions))} addition{'s' if num_additions != 1 else ''}"
        deletion_text = f"{Styles.bold(str(num_deletions))} removal{'s' if num_deletions != 1 else ''}"
        return Box()[
            Text(f"Updated {Styles.bold(get_relative_path(args['file_path']))} with {addition_text} and {deletion_text}"),
            Diff(diff=args['diff'])
        ]


# Components

def Prompt(text: TextPrompt) -> Component:
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("> ", Theme.GRAY)),
            Text(Colors.hex(text.text, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("  ⎿  ", Theme.GRAY)),
            Text(Colors.hex(text.error, Theme.RED))
        ] if text.error else None,
    ]

def ShellCall(command: ShellCommand, elapsed: float, expanded: bool = True) -> Component:
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("! ", Theme.PINK)),
            Text(Colors.hex(command.command, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(get_shell_output(command.output, command.status, elapsed, expanded))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(Colors.hex(command.error, Theme.RED))
        ] if command.status is Status.COMPLETED and command.error else None,
    ]

def TextResponse(text: TextContent) -> Component:
    return Box(flex=Flex.HORIZONTAL, margin={'top': 1})[
        Text("● "),
        Text(render_markdown(text.text))
    ]

def ToolCall(request: ToolRequest, response: ToolResponse | None, expanded: bool = True) -> Component:
    tool = TOOLS[request.tool]
    status = response.status if response else Status.PENDING
    result = response.response if response else ''
    args_str = tool.render_args(request.arguments)

    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("● ", STATUS_COLORS[status])),
            Text(Styles.bold(tool.name) + (f"({args_str})" if args_str else ''))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            get_edit_result(request.processed_arguments or {}, result, status, expanded)
                if tool in (TOOLS['Edit'], TOOLS['Write'])
                else Text(get_tool_result(tool, request.arguments, result, status, expanded))
        ],
    ]
