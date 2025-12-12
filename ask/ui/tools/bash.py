from typing import ClassVar
from dataclasses import dataclass

from ask.ui.tools.base import ToolOutput, ToolOutputController, abbreviate

@dataclass
class BashToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: BashToolOutputController

class BashToolOutputController(ToolOutputController):
    def get_name(self) -> str:
        return "Bash"

    def get_args(self) -> str:
        return self.props.request.arguments['command']

    def get_short_response(self, response: str) -> str:
        return abbreviate(response, max_lines=3)
