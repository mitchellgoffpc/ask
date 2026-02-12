from dataclasses import dataclass

from ask.messages import Blob, Text, ToolRequest, ToolResponse, ToolCallStatus
from ask.ui.core import UI, Axis, Colors, Styles, Theme

STATUS_COLORS = {
    ToolCallStatus.PENDING: Theme.GRAY,
    ToolCallStatus.COMPLETED: Theme.GREEN,
    ToolCallStatus.CANCELLED: Theme.RED,
    ToolCallStatus.FAILED: Theme.RED
}

def abbreviate(text: str, max_lines: int) -> str:
    lines = text.strip().split('\n')
    if len(lines) <= max_lines:
        return text.strip()
    abbreviated = '\n'.join(lines[:max_lines])
    expand_text = Colors.hex(f"… +{len(lines) - max_lines} lines (ctrl+r to expand)", Theme.GRAY)
    return f"{abbreviated}\n{expand_text}"


@dataclass
class ToolOutput(UI.Widget):
    request: ToolRequest
    response: ToolResponse | None
    expanded: bool

class ToolOutputController(UI.Controller[ToolOutput]):
    def get_name(self) -> str:
        return self.props.request.tool

    def get_args(self) -> str:
        raise NotImplementedError()

    def get_short_response(self, response: str) -> str:
        raise NotImplementedError()

    def get_full_response(self, response: str) -> str:
        return response

    def get_error_message(self, error: str) -> UI.Component:
        return UI.Text(Colors.hex(f"Error: {error}", Theme.RED))

    def get_completed_output(self, response: Blob) -> UI.Component:
        assert isinstance(response, Text)
        if not response.text.strip():
            return UI.Text(Colors.hex("(No content)", Theme.GRAY))
        elif self.props.expanded:
            return UI.Text(self.get_full_response(response.text))
        else:
            return UI.Text(self.get_short_response(response.text))

    def get_tool_output(self) -> UI.Component:
        status = self.props.response.status if self.props.response else ToolCallStatus.PENDING
        if status is ToolCallStatus.PENDING:
            return UI.Text(Colors.hex("Running…", Theme.GRAY))
        elif status is ToolCallStatus.CANCELLED:
            return UI.Text(Colors.hex("Interrupted", Theme.RED))
        elif status is ToolCallStatus.FAILED:
            assert self.props.response is not None
            assert isinstance(self.props.response.response, Text)
            return self.get_error_message(self.props.response.response.text)
        elif status is ToolCallStatus.COMPLETED:
            assert self.props.response is not None
            return self.get_completed_output(self.props.response.response)
        else:
            raise ValueError(f"Unknown status: {status}")

    def contents(self) -> list[UI.Component | None]:
        return [
            UI.Box(flex=Axis.HORIZONTAL)[
                UI.Text(Colors.hex("● ", STATUS_COLORS[self.props.response.status if self.props.response else ToolCallStatus.PENDING])),
                UI.Text(f"{Styles.bold(self.get_name())} {self.get_args()}"),

            ],
            UI.Box(flex=Axis.HORIZONTAL)[
                UI.Text("  ⎿  "),
                self.get_tool_output(),
            ]
        ]
