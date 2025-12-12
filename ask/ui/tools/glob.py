from typing import ClassVar
from dataclasses import dataclass

from ask.prompts import get_relative_path
from ask.ui.core.styles import Styles
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class GlobToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: GlobToolOutputController

class GlobToolOutputController(ToolOutputController):
    def get_args(self) -> str:
        args = self.props.request.processed_arguments or {}
        path = get_relative_path(args['path'])
        return f'pattern: "{args["pattern"]}", path: "{path}"'

    def get_short_response(self, response: str) -> str:
        file_count = len(response.strip().split('\n'))
        return f"Found {Styles.bold(file_count - 1)} files"
