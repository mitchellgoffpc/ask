from dataclasses import dataclass

from ask.messages import Text, ToolCallStatus
from ask.prompts import get_relative_path
from ask.ui.core import UI, Axis, Colors, Styles, Theme
from ask.ui.tools.base import STATUS_COLORS, ToolOutput, ToolOutputController
from ask.ui.tools.diff import Diff


@dataclass
class EditToolOutput(ToolOutput):
    class Controller(ToolOutputController):
        def get_args(self) -> str:
            artifacts = self.props.request.artifacts
            num_additions = sum(1 for line in artifacts['diff'] if line.startswith('+') and not line.startswith('+++'))
            num_deletions = sum(1 for line in artifacts['diff'] if line.startswith('-') and not line.startswith('---'))
            addition_text = Colors.hex(f"+{num_additions}", Theme.GREEN)
            deletion_text = Colors.hex(f"-{num_deletions}", Theme.RED)
            return f"{get_relative_path(self.props.request.arguments['file_path'])} ({addition_text} {deletion_text})"

        def get_tool_output(self) -> UI.Component:
            match self.props.response.status if self.props.response else ToolCallStatus.PENDING:
                case ToolCallStatus.COMPLETED | ToolCallStatus.PENDING :
                    return Diff(diff=self.props.request.artifacts['diff'])
                case ToolCallStatus.CANCELLED:
                    return UI.Box()[
                        UI.Text("  ⎿  " + Colors.hex("Rejected by user", Theme.RED)),
                        Diff(diff=self.props.request.artifacts['diff'], rejected=True),
                    ]
                case ToolCallStatus.FAILED:
                    assert self.props.response is not None
                    assert isinstance(self.props.response.response, Text)
                    return UI.Box(flex=Axis.HORIZONTAL)[
                        UI.Text("  ⎿  "),
                        self.get_error_message(self.props.response.response.text),
                    ]
                case _:
                    return UI.Text("  ⎿  ")

        def contents(self) -> list[UI.Component | None]:
            return [
                UI.Box(flex=Axis.HORIZONTAL)[
                    UI.Text(Colors.hex("● ", STATUS_COLORS[self.props.response.status if self.props.response else ToolCallStatus.PENDING])),
                    UI.Text(f"{Styles.bold(self.get_name())} {self.get_args()}"),
                ],
                self.get_tool_output(),
            ]
