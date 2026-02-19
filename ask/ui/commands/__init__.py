from ask.commands import BashCommand, SlashCommand
from ask.messages import Error, Text, ToolCallStatus, ToolRequest, ToolResponse
from ask.ui.core import UI, Axis, Colors, render_markdown
from ask.ui.theme import Theme
from ask.ui.tools import TOOL_COMPONENTS

NUM_PREVIEW_LINES = 5
STATUS_COLORS = {
    ToolCallStatus.PENDING: '',
    ToolCallStatus.COMPLETED: Theme.GREEN,
    ToolCallStatus.CANCELLED: Theme.RED,
    ToolCallStatus.FAILED: Theme.RED}

def get_bash_output(stdout: str, stderr: str, status: ToolCallStatus, elapsed: float) -> tuple[str, str]:
    if status is ToolCallStatus.PENDING:
        return "Running…" + (f" ({int(elapsed)}s)" if elapsed >= 1 else ""), ''
    elif status is ToolCallStatus.CANCELLED:
        return stdout, "Interrupted"
    elif status is ToolCallStatus.FAILED:
        return stdout, stderr or "Bash exited with non-zero exit code"
    elif status is ToolCallStatus.COMPLETED:
        result = stdout + stderr
        if not result.strip():
            return "(No content)", ''
        else:
            return result, ''


# Components

def PromptMessage(text: Text) -> UI.Component | None:
    return UI.Box(flex=Axis.HORIZONTAL, width=1.0, margin={'top': 1}, padding={'bottom': 1, 'top': 1}, background_color=Theme.background())[
        UI.Text(">", margin={'left': 1, 'right': 1}),
        UI.Text(text.text),
    ] if text.text.strip() else None

def ResponseMessage(text: Text) -> UI.Component:
    return UI.Box(flex=Axis.HORIZONTAL, margin={'top': 1})[
        UI.Text("● "),
        UI.Text(render_markdown(text.text, code_color=Theme.BLUE)),
    ]

def ErrorMessage(error: Error) -> UI.Component:
    return UI.Box(flex=Axis.HORIZONTAL)[
        UI.Text("  ⎿  "),
        UI.Text(Colors.hex(error.text, Theme.RED)),
    ]

def ToolCallMessage(request: ToolRequest, response: ToolResponse | None, expanded: bool) -> UI.Component:
    return UI.Box(margin={'top': 1})[
        TOOL_COMPONENTS[request.tool](request, response, expanded)
    ]

def SlashCommandMessage(command: SlashCommand) -> UI.Component:
    return UI.Box()[
        PromptMessage(text=Text(command.command)),
        UI.Box(margin={'top': 1})[
            UI.Text(command.output) if command.output else None,
            UI.Text(Colors.hex(command.error, Theme.RED)) if command.error else None,
        ] if command.output or command.error else None,
    ]

def BashCommandMessage(command: BashCommand, elapsed: float) -> UI.Component:
    output, error = get_bash_output(command.stdout, command.stderr, command.status, elapsed)
    return UI.Box(margin={'top': 1})[
        UI.Box(flex=Axis.HORIZONTAL)[
            UI.Text(Colors.hex("! ", Theme.PINK)),
            UI.Text(command.command),
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

