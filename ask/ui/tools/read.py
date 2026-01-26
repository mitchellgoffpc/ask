from typing import ClassVar
from dataclasses import dataclass

from ask.messages import Blob, Image, PDF
from ask.prompts import get_relative_path
from ask.ui.core import UI, Styles
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class ReadToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: ReadToolOutputController

class ReadToolOutputController(ToolOutputController):
    def get_args(self) -> str:
        return get_relative_path(self.props.request.arguments['file_path'])

    def get_short_response(self, response: str) -> str:
        line_count = response.count('\n') + 1
        return f"Read {Styles.bold(line_count)} lines"

    def get_response(self, response: str) -> str:
        return '\n'.join(line.split('→')[-1] for line in response.split('\n'))

    def get_completed_output(self, response: Blob) -> UI.Component:
        match response:
            case Image(): return UI.Text("Read Image")
            case PDF(): return UI.Text("Read PDF")
            case _: return super().get_completed_output(response)
