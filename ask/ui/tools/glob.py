from dataclasses import dataclass

from ask.prompts import get_relative_path
from ask.ui.core import Styles
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class GlobToolOutput(ToolOutput):
    class Controller(ToolOutputController):
        def get_args(self) -> str:
            path = get_relative_path(self.props.request.arguments['path'])
            return f'pattern: "{self.props.request.arguments["pattern"]}", path: "{path}"'

        def get_short_response(self, response: str) -> str:
            file_count = len(response.strip().split('\n'))
            return f"Found {Styles.bold(file_count - 1)} files"
