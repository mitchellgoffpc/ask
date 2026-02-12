from ask.commands import PythonCommand, BashCommand, SlashCommand
from ask.messages import Text, ToolRequest, ToolResponse, Error, ToolCallStatus
from ask.ui.core import UI, Axis, Colors, Theme, render_markdown
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

def PromptMessage(text: Text) -> UI.Component | None:
    return UI.Box(flex=Axis.HORIZONTAL, margin={'top': 1})[
        UI.Text(Colors.hex("> ", Theme.GRAY)),
        UI.Text(Colors.hex(text.text, Theme.GRAY)),
    ] if text.text.strip() else None

def ResponseMessage(text: Text) -> UI.Component:
    return UI.Box(flex=Axis.HORIZONTAL, margin={'top': 1})[
        UI.Text("● "),
        UI.Text(render_markdown(text.text)),
    ]

def ErrorMessage(error: Error) -> UI.Component:
    return UI.Box(flex=Axis.HORIZONTAL)[
        UI.Text(Colors.hex("  ⎿  ", Theme.GRAY)),
        UI.Text(Colors.hex(error.text, Theme.RED)),
    ]

def ToolCallMessage(request: ToolRequest, response: ToolResponse | None, expanded: bool) -> UI.Component:
    return UI.Box(margin={'top': 1})[
        TOOL_COMPONENTS[request.tool](request, response, expanded)
    ]

def SlashCommandMessage(command: SlashCommand) -> UI.Component:
    return UI.Box()[
        PromptMessage(Text(command.render_command())),
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text(Colors.hex("  ⎿  ", Theme.GRAY)),
            UI.Text(Colors.hex(command.output, Theme.GRAY)),
        ] if command.output else None,
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text("  ⎿  "),
            UI.Text(Colors.hex(command.error, Theme.RED)),
        ] if command.error else None,
    ]

def BashCommandMessage(command: BashCommand, elapsed: float) -> UI.Component:
    output, error = get_bash_output(command.stdout, command.stderr, command.status, elapsed)
    return UI.Box(margin={'top': 1})[
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text(Colors.hex("! ", Theme.PINK)),
            UI.Text(Colors.hex(command.command, Theme.GRAY)),
        ],
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text("  ⎿  "),
            UI.Text(output),
        ] if output else None,
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text("  ⎿  "),
            UI.Text(Colors.hex(error, Theme.RED)),
        ] if error else None,
    ]

def PythonCommandMessage(command: PythonCommand, elapsed: float) -> UI.Component:
    output, error = get_bash_output(command.output, command.error, command.status, elapsed)
    return UI.Box(margin={'top': 1})[
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text(Colors.hex(">>> ", Theme.GREEN)),
            UI.Text(Colors.hex(command.command, Theme.GRAY)),
        ],
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text("  ⎿  "),
            UI.Text(output),
        ] if output else None,
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text("  ⎿  "),
            UI.Text(error),
        ] if error else None,
    ]
