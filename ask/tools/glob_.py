import glob
from pathlib import Path
from typing import Any

from ask.messages import Blob, Text
from ask.prompts import load_tool_prompt
from ask.tools.base import Tool, Parameter, ParameterType, ToolError


class GlobTool(Tool):
    name = "Glob"
    description = load_tool_prompt('glob')
    parameters = [
        Parameter("path", "The absolute path of the directory to search in (must be absolute, not relative)", ParameterType.String),
        Parameter("pattern", "The glob pattern to match files against", ParameterType.String)]

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        self.check_absolute_path(Path(args['path']), is_file=False)
        return {'path': Path(args['path']), 'pattern': args['pattern']}

    async def run(self, path: Path, pattern: str) -> Blob:
        try:
            matches = glob.glob(str(path / pattern), recursive=True)
            matches = [m for m in matches if Path(m).is_file()]
            matches.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
            return Text(f"Found {len(matches)} files" + ''.join(f'\n- {m}' for m in matches))
        except PermissionError:
            return Text("Found 0 files")
        except Exception as e:
            raise ToolError(f"An error occurred while searching for pattern '{pattern}' in '{path}': {str(e)}") from e
