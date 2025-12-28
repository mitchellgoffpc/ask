from dataclasses import dataclass
from typing import Any

from ask.messages import Blob, Text as TextContent, ToolRequest, ToolResponse, ToolCallStatus
from ask.ui.core.components import Component, Controller, Box, Text, Widget
from ask.ui.core.styles import Flex, Colors, Styles, Theme

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
class ToolOutput(Widget):
    request: ToolRequest
    response: ToolResponse | None
    expanded: bool

class ToolOutputController(Controller[ToolOutput]):
    def get_name(self) -> str:
        return self.props.request.tool

    def get_args(self, args: dict[str, Any]) -> str:
        raise NotImplementedError()

    def get_short_response(self, response: str) -> str:
        raise NotImplementedError()

    def get_full_response(self, response: str) -> str:
        return response

    def get_error_message(self, error: str) -> Component:
        return Text(Colors.hex(f"Error: {error}", Theme.RED))

    def get_completed_output(self, response: Blob) -> Component:
        assert isinstance(response, TextContent)
        if not response.text.strip():
            return Text(Colors.hex("(No content)", Theme.GRAY))
        elif self.props.expanded:
            return Text(self.get_full_response(response.text))
        else:
            return Text(self.get_short_response(response.text))

    def get_tool_output(self) -> Component:
        status = self.props.response.status if self.props.response else ToolCallStatus.PENDING
        if status is ToolCallStatus.PENDING:
            return Text(Colors.hex("Running…", Theme.GRAY))
        elif status is ToolCallStatus.CANCELLED:
            return Text(Colors.hex("Interrupted", Theme.RED))
        elif status is ToolCallStatus.FAILED:
            assert self.props.response is not None
            assert isinstance(self.props.response.response, TextContent)
            return self.get_error_message(self.props.response.response.text)
        elif status is ToolCallStatus.COMPLETED:
            assert self.props.response is not None
            return self.get_completed_output(self.props.response.response)

    def contents(self) -> list[Component | None]:
        args = self.props.request.processed_arguments
        return [
            Box(flex=Flex.HORIZONTAL)[
                Text(Colors.hex("● ", STATUS_COLORS[self.props.response.status if self.props.response else ToolCallStatus.PENDING])),
                Text(f"{Styles.bold(self.get_name())} {self.get_args(args) if args else ''}"),
            ],
            Box(flex=Flex.HORIZONTAL)[
                Text("  ⎿  "),
                self.get_tool_output(),
            ]
        ]
