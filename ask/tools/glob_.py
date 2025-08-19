import glob
from pathlib import Path
from typing import Any

from ask.prompts import load_tool_prompt
from ask.tools.base import Tool, Parameter, ToolError
from ask.ui.styles import Styles


class GlobTool(Tool):
    name = "Glob"
    description = load_tool_prompt('glob')
    parameters = [
        Parameter("path", "string", "The absolute path of the directory to search in (must be absolute, not relative)"),
        Parameter("pattern", "string", "The glob pattern to match files against")]

    def render_args(self, args: dict[str, str]) -> str:
        try:
            path = str(Path(args['path']).relative_to(Path.cwd()))
        except ValueError:
            path = args['path']
        return f'pattern: "{args["pattern"]}", path: "{path}"'

    def render_short_response(self, response: str) -> str:
        file_count = len(response.strip().split('\n'))
        return f"Found {Styles.bold(file_count - 1)} files"

    async def run(self, args: dict[str, Any]) -> str:
        path = Path(args['path'])
        if not path.is_absolute():
            raise ToolError(f"Path '{path}' is not an absolute path. Please provide an absolute path.")
        if not path.exists():
            raise ToolError(f"Path '{path}' does not exist.")
        if not path.is_dir():
            raise ToolError(f"Path '{path}' is not a directory.")

        try:
            matches = glob.glob(str(path / args["pattern"]), recursive=True)
            matches = [m for m in matches if Path(m).is_file()]
            matches.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
            return f"Found {len(matches)} files" + ''.join(f'\n- {m}' for m in matches)
        except PermissionError:
            return "Found 0 files"
        except Exception as e:
            raise ToolError(f"An error occurred while searching for pattern '{args['pattern']}' in '{path}': {str(e)}") from e
