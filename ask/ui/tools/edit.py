from typing import Any, ClassVar
from dataclasses import dataclass

from ask.messages import Text as TextContent, ToolCallStatus
from ask.prompts import get_relative_path
from ask.ui.core.components import Component, Box, Text
from ask.ui.core.diff import Diff
from ask.ui.core.styles import Styles, Colors, Theme, Flex
from ask.ui.tools.base import STATUS_COLORS, ToolOutput, ToolOutputController

@dataclass
class EditToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: EditToolOutputController

class EditToolOutputController(ToolOutputController):
    def get_args(self, args: dict[str, Any]) -> str:
        num_additions = sum(1 for line in args['diff'] if line.startswith('+') and not line.startswith('+++'))
        num_deletions = sum(1 for line in args['diff'] if line.startswith('-') and not line.startswith('---'))
        addition_text = Colors.hex(f"+{num_additions}", Theme.GREEN)
        deletion_text = Colors.hex(f"-{num_deletions}", Theme.RED)
        return f"{get_relative_path(args['file_path'])} ({addition_text} {deletion_text})"

    def get_cancelled_message(self, args: dict[str, Any]) -> Component:
        return Box()[
            Text("  ⎿  " + Colors.hex("Rejected by user", Theme.RED)),
            Diff(diff=args['diff'], rejected=True)
        ]

    def get_diff(self, args: dict[str, Any]) -> Component:
        return Diff(diff=args['diff'])

    def get_tool_output(self) -> Component:
        args = self.props.request.processed_arguments
        match self.props.response.status if self.props.response else ToolCallStatus.PENDING:
            case ToolCallStatus.COMPLETED | ToolCallStatus.PENDING if args:
                return self.get_diff(args)
            case ToolCallStatus.CANCELLED if args:
                return self.get_cancelled_message(args)
            case ToolCallStatus.FAILED:
                assert self.props.response is not None
                assert isinstance(self.props.response.response, TextContent)
                return Box(flex=Flex.HORIZONTAL)[
                    Text("  ⎿  "),
                    self.get_error_message(self.props.response.response.text),
                ]
            case _:
                return Text("  ⎿  ")

    def contents(self) -> list[Component | None]:
        args = self.props.request.processed_arguments
        return [
            Box(flex=Flex.HORIZONTAL)[
                Text(Colors.hex("● ", STATUS_COLORS[self.props.response.status if self.props.response else ToolCallStatus.PENDING])),
                Text(f"{Styles.bold(self.get_name())} {self.get_args(args) if args else ''}"),
            ],
            self.get_tool_output(),
        ]
