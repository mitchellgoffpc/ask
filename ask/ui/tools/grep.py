from dataclasses import dataclass
from pathlib import Path

from ask.prompts import get_relative_path
from ask.ui.core import Styles
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class GrepToolOutput(ToolOutput):
    class Controller(ToolOutputController):
        def get_args(self) -> str:
            pattern = self.props.request.arguments.get('pattern', '')
            if len(pattern) > 50:
                pattern = pattern[:47] + "..."
            path = get_relative_path(self.props.request.arguments.get('pathspec', Path.cwd()))
            return f'pattern: "{pattern}", path: "{path}"'

        def get_short_response(self, response: str) -> str:
            if response.startswith("Found "):
                return f"Found {Styles.bold(response.split()[1])} matches"
            elif "No matches found" in response:
                return "No matches found"
            else:
                return "Search completed"
