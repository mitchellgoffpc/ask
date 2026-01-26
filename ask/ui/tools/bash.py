from typing import ClassVar
from dataclasses import dataclass

from ask.messages import Text as TextContent
from ask.ui.core import Component, Text, Box, Axis, Colors, Theme, highlight_code
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class BashToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: BashToolOutputController

class BashToolOutputController(ToolOutputController):
    def contents(self) -> list[Component | None]:
        lines = highlight_code(self.props.request.arguments['command'], language='bash').strip().split('\n')
        return [
            *[Box(flex=Axis.HORIZONTAL)[
                Text(Colors.hex('>>> ' if i == 0 else '... ', Theme.PINK)),
                Text(line)
            ] for i, line in enumerate(lines)],
            Text(self.props.response.response.text.strip())
                if self.props.response and isinstance(self.props.response.response, TextContent) else None,
        ]
