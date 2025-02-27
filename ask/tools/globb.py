import glob
from pathlib import Path
from typing import Any
from ask.tools.base import Tool, Parameter

GLOB_TOOL_DESCRIPTION = """
- Fast file pattern matching tool that works with any codebase size
- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Returns matching file paths sorted by modification time
- Use this tool when you need to find files by name patterns
""".strip()

PATH_ARG_DESCRIPTION = "The absolute path to the directory to search in (must be absolute, not relative). Defaults to the current working directory."

class GlobTool(Tool):
    name = "glob"
    description = GLOB_TOOL_DESCRIPTION
    parameters = [
        Parameter("pattern", "string", "The glob pattern to match files against"),
        Parameter("path", "string", PATH_ARG_DESCRIPTION, required=False)]

    @classmethod
    def run(cls, args: dict[str, Any]) -> str:
        path = Path(args.get("path", Path.cwd()))
        if not path.is_absolute():
            return f"Error: Path '{path}' is not an absolute path. Please provide an absolute path."
        if not path.exists():
            return f"Error: Path '{path}' does not exist."
        if not path.is_dir():
            return f"Error: Path '{path}' is not a directory."

        try:
            matches = glob.glob(str(path / args["pattern"]), recursive=True)
            matches = [m for m in matches if Path(m).is_file()]
            matches.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
            return '\n'.join(matches)
        except PermissionError:
            return f"Error: Permission denied for path '{path}'."
        except Exception as e:
            return f"Error: {str(e)}"
