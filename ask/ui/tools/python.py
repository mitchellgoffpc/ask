from typing import ClassVar
from dataclasses import dataclass

from ask.models import Text as TextContent
from ask.ui.core.components import Component, Text, Box
from ask.ui.core.markdown_ import highlight_code
from ask.ui.core.styles import Colors, Flex, Theme
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class PythonToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: PythonToolOutputController

class PythonToolOutputController(ToolOutputController):
    def contents(self) -> list[Component | None]:
        if not (args := self.props.request.processed_arguments):
            return []
        lines = highlight_code(args['code'], language='python').strip().split('\n')

        return [
            *[Box(flex=Flex.HORIZONTAL)[
                Text(Colors.hex('>>> ' if i == 0 else '... ', Theme.GREEN)),
                Text(line)
            ] for i, line in enumerate(lines)],
            Text(self.props.response.response.text.strip())
                if self.props.response and isinstance(self.props.response.response, TextContent) else None,
        ]
