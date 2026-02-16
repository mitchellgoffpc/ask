from dataclasses import dataclass

from ask.messages import Text
from ask.ui.core import UI, Axis, Colors, highlight_code
from ask.ui.theme import Theme
from ask.ui.tools.base import ToolOutput, ToolOutputController


@dataclass
class BashToolOutput(ToolOutput):
    class Controller(ToolOutputController):
        def contents(self) -> list[UI.Component | None]:
            lines = highlight_code(self.props.request.arguments['command'], language='bash').strip().split('\n')
            return [
                *[UI.Box(flex=Axis.HORIZONTAL)[
                    UI.Text(Colors.hex('>>> ' if i == 0 else '... ', Theme.PINK)),
                    UI.Text(line),
                ] for i, line in enumerate(lines)],
                UI.Text(self.props.response.response.text.strip())
                    if self.props.response and isinstance(self.props.response.response, Text) else None,
            ]
