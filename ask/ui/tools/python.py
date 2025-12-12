from typing import ClassVar
from dataclasses import dataclass

from ask.tools import ToolCallStatus
from ask.ui.core.components import Component, Text, Box
from ask.ui.core.markdown_ import highlight_code
from ask.ui.core.styles import Colors, Flex, Styles
from ask.ui.tools.base import STATUS_COLORS, ToolOutput, ToolOutputController, abbreviate

@dataclass
class PythonToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: PythonToolOutputController

class PythonToolOutputController(ToolOutputController):
    def get_code(self) -> str:
        args = self.props.request.processed_arguments or {}
        code = highlight_code(args['code'], language='python')
        return abbreviate(code, max_lines=10) if not self.props.expanded else code

    def get_short_response(self, response: str) -> str:
        return abbreviate(self.get_response(response), max_lines=6)

    def get_response(self, response: str) -> str:
        return response.strip()

    def contents(self) -> list[Component | None]:
        status = self.props.response.status if self.props.response else ToolCallStatus.PENDING

        return [
            Box(flex=Flex.HORIZONTAL)[
                Text(Colors.hex("● ", STATUS_COLORS[status])),
                Text(Styles.bold("Python")),
            ],
            Box(flex=Flex.HORIZONTAL, margin={'bottom': 1})[
                Text("  ⎿  "),
                Text(self.get_code())
            ] if self.props.approved else None,
            Box(flex=Flex.HORIZONTAL)[
                Text("  ⎿  "),
                self.get_tool_output(),
            ]
        ]
