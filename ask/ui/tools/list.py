from typing import Any, ClassVar
from dataclasses import dataclass

from ask.prompts import get_relative_path
from ask.ui.core.styles import Styles
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class ListToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: ListToolOutputController

class ListToolOutputController(ToolOutputController):
    def get_args(self, args: dict[str, Any]) -> str:
        return get_relative_path(args['path'])

    def get_short_response(self, response: str) -> str:
        item_count = response.count('\n') + 1
        return f"Listed {Styles.bold(item_count)} paths"
