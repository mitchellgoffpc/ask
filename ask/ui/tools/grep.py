from typing import ClassVar
from dataclasses import dataclass
from pathlib import Path

from ask.prompts import get_relative_path
from ask.ui.core.styles import Styles
from ask.ui.tools.base import ToolOutput, ToolOutputController

@dataclass
class GrepToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: GrepToolOutputController

class GrepToolOutputController(ToolOutputController):
    def get_args(self) -> str:
        args = self.props.request.processed_arguments or {}
        pattern = args.get('pattern', '')
        if len(pattern) > 50:
            pattern = pattern[:47] + "..."
        path = get_relative_path(args.get('pathspec', Path.cwd()))
        return f'pattern: "{pattern}", path: "{path}"'

    def get_short_response(self, response: str) -> str:
        if response.startswith("Found "):
            match_count = response.split()[1]
            return f"Found {Styles.bold(match_count)} matches"
        elif "No matches found" in response:
            return "No matches found"
        else:
            return "Search completed"
