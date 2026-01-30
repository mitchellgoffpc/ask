from dataclasses import dataclass

from ask.prompts import get_relative_path
from ask.ui.core import Styles
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class ListToolOutput(ToolOutput):
    class Controller(ToolOutputController):
        def get_args(self) -> str:
            return get_relative_path(self.props.request.arguments['path'])

        def get_short_response(self, response: str) -> str:
            item_count = response.count('\n') + 1
            return f"Listed {Styles.bold(item_count)} paths"
