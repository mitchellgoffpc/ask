from typing import Any, cast

from ask.models import Text as TextContent, Image, ToolRequest, ToolResponse, Error
from ask.prompts import get_relative_path
from ask.tools import TOOLS, Tool, ToolCallStatus, EditTool, MultiEditTool, PythonTool, WriteTool
from ask.ui.commands import ShellCommand, SlashCommand
from ask.ui.components import Component, Box, Text
from ask.ui.diff import Diff
from ask.ui.markdown_ import render_markdown
from ask.ui.styles import Flex, Colors, Styles, Theme

NUM_PREVIEW_LINES = 5
STATUS_COLORS = {
    ToolCallStatus.PENDING: Theme.GRAY,
    ToolCallStatus.COMPLETED: Theme.GREEN,
    ToolCallStatus.CANCELLED: Theme.RED,
    ToolCallStatus.FAILED: Theme.RED}

def get_shell_output(stdout: str, stderr: str, status: ToolCallStatus, elapsed: float, expanded: bool) -> tuple[str, str]:
    if status is ToolCallStatus.PENDING:
        return Colors.hex("Running…" + (f" ({int(elapsed)}s)" if elapsed >= 1 else ""), Theme.GRAY), ''
    elif status is ToolCallStatus.CANCELLED:
        return stdout, "Interrupted"
    elif status is ToolCallStatus.FAILED:
        return stdout, stderr or "Bash exited with non-zero exit code"
    elif status is ToolCallStatus.COMPLETED:
        result = stdout + stderr
        if not result.strip():
            return Colors.hex("(No content)", Theme.GRAY), ''
        elif expanded:
            return result, ''
        else:
            lines = result.rstrip('\n').split('\n')
            expand_text = Colors.hex(f"… +{len(lines) - NUM_PREVIEW_LINES} lines (ctrl+r to expand)", Theme.GRAY)
            return '\n'.join(lines[:NUM_PREVIEW_LINES]) + (f'\n{expand_text}' if len(lines) > NUM_PREVIEW_LINES else ''), ''

def get_tool_result(tool: Tool, args: dict[str, Any], result: TextContent | Image | None, status: ToolCallStatus, expanded: bool) -> str:
    if status is ToolCallStatus.PENDING:
        return Colors.hex("Running…", Theme.GRAY)
    elif status is ToolCallStatus.CANCELLED:
        return Colors.hex("Interrupted", Theme.RED)
    elif status is ToolCallStatus.FAILED:
        assert isinstance(result, TextContent)
        return Colors.hex(tool.render_error(result.text), Theme.RED)
    elif status is ToolCallStatus.COMPLETED:
        assert result is not None
        if isinstance(result, TextContent) and not result.text.strip():
            return Colors.hex("(No content)", Theme.GRAY)
        elif isinstance(result, Image):
            return tool.render_image_response(args, result.data)
        elif expanded:
            return tool.render_response(args, result.text)
        else:
            return tool.render_short_response(args, result.text)

def get_edit_result(args: dict[str, Any], result: TextContent | Image | None, status: ToolCallStatus, expanded: bool) -> Component:
    if status is ToolCallStatus.PENDING:
        return Text(Colors.hex("Waiting…", Theme.GRAY))
    elif status is ToolCallStatus.FAILED:
        assert isinstance(result, TextContent)
        return Text(Colors.hex(result.text, Theme.RED))
    elif status is ToolCallStatus.CANCELLED:
        operation = 'update' if args['old_content'] else 'write'
        return Box()[
            Text(Colors.hex(f"User rejected {operation} to {Styles.bold(get_relative_path(args['file_path']))}", Theme.RED)),
            Diff(diff=args['diff'], rejected=True)
        ]
    elif status is ToolCallStatus.COMPLETED and not args['old_content']:
        return Text(get_tool_result(TOOLS[WriteTool.name], args, result, status, expanded))
    elif status is ToolCallStatus.COMPLETED:
        num_additions = sum(1 for line in args['diff'] if line.startswith('+') and not line.startswith('+++'))
        num_deletions = sum(1 for line in args['diff'] if line.startswith('-') and not line.startswith('---'))
        addition_text = f"{Styles.bold(str(num_additions))} addition{'s' if num_additions != 1 else ''}"
        deletion_text = f"{Styles.bold(str(num_deletions))} removal{'s' if num_deletions != 1 else ''}"
        return Box()[
            Text(f"Updated {Styles.bold(get_relative_path(args['file_path']))} with {addition_text} and {deletion_text}"),
            Diff(diff=args['diff'])
        ]


# Components

def PromptMessage(text: TextContent) -> Component:
    return Box(flex=Flex.HORIZONTAL, margin={'top': 1})[
        Text(Colors.hex("> ", Theme.GRAY)),
        Text(Colors.hex(text.text, Theme.GRAY))
    ]

def ResponseMessage(text: TextContent) -> Component:
    return Box(flex=Flex.HORIZONTAL, margin={'top': 1})[
        Text("● "),
        Text(render_markdown(text.text))
    ]

def ErrorMessage(error: Error) -> Component:
    return Box(flex=Flex.HORIZONTAL)[
        Text(Colors.hex("  ⎿  ", Theme.GRAY)),
        Text(Colors.hex(error.text, Theme.RED))
    ]

def ToolCallMessage(request: ToolRequest, response: ToolResponse | None, approved: bool, expanded: bool) -> Component:
    tool = TOOLS[request.tool]
    status = response.status if response else ToolCallStatus.PENDING
    args_str = tool.render_args(request.arguments)
    response_content = response.response if response else None
    python_tool = cast(PythonTool, TOOLS[PythonTool.name])

    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("● ", STATUS_COLORS[status])),
            Text(Styles.bold(tool.render_name()) + (f"({args_str})" if args_str else ''))
        ],
        Box(flex=Flex.HORIZONTAL, margin={'bottom': 1})[
            Text("  ⎿  "),
            Text(python_tool.render_code(request.arguments) if expanded else python_tool.render_short_code(request.arguments))
        ] if tool.name == PythonTool.name and approved else None,
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            get_edit_result(request.processed_arguments or {}, response_content, status, expanded)
                if tool.name in (EditTool.name, MultiEditTool.name, WriteTool.name)
                else Text(get_tool_result(tool, request.processed_arguments or {}, response_content, status, expanded))
        ],
    ]

def SlashCommandMessage(command: SlashCommand) -> Component:
    return Box()[
        PromptMessage(TextContent(command.render_command())),
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("  ⎿  ", Theme.GRAY)),
            Text(Colors.hex(command.output, Theme.GRAY))
        ] if command.output else None,
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(Colors.hex(command.error, Theme.RED))
        ] if command.error else None,
    ]

def ShellCommandMessage(command: ShellCommand, elapsed: float, expanded: bool) -> Component:
    output, error = get_shell_output(command.stdout, command.stderr, command.status, elapsed, expanded)
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("! ", Theme.PINK)),
            Text(Colors.hex(command.command, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(output)
        ] if output else None,
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(Colors.hex(error, Theme.RED))
        ] if error else None,
    ]
