from ask.commands import PythonCommand, BashCommand, SlashCommand
from ask.messages import Text as TextContent, CheckedToolRequest, ToolResponse, Error, ToolCallStatus
from ask.ui.core.components import Component, Box, Text
from ask.ui.core.markdown_ import render_markdown
from ask.ui.core.styles import Flex, Colors, Theme
from ask.ui.tools import TOOL_COMPONENTS

NUM_PREVIEW_LINES = 5
STATUS_COLORS = {
    ToolCallStatus.PENDING: Theme.GRAY,
    ToolCallStatus.COMPLETED: Theme.GREEN,
    ToolCallStatus.CANCELLED: Theme.RED,
    ToolCallStatus.FAILED: Theme.RED}

def get_bash_output(stdout: str, stderr: str, status: ToolCallStatus, elapsed: float) -> tuple[str, str]:
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
        else:
            return result, ''


# Components

def PromptMessage(text: TextContent) -> Component | None:
    return Box(flex=Flex.HORIZONTAL, margin={'top': 1})[
        Text(Colors.hex("> ", Theme.GRAY)),
        Text(Colors.hex(text.text, Theme.GRAY))
    ] if text.text.strip() else None

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

def ToolCallMessage(request: CheckedToolRequest, response: ToolResponse | None, expanded: bool) -> Component:
    return Box(margin={'top': 1})[
        TOOL_COMPONENTS[request.tool](request, response, expanded)
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

def BashCommandMessage(command: BashCommand, elapsed: float) -> Component:
    output, error = get_bash_output(command.stdout, command.stderr, command.status, elapsed)
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

def PythonCommandMessage(command: PythonCommand, elapsed: float) -> Component:
    output, error = get_bash_output(command.output, command.error, command.status, elapsed)
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex(">>> ", Theme.GREEN)),
            Text(Colors.hex(command.command, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(output)
        ] if output else None,
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(error)
        ] if error else None,
    ]
