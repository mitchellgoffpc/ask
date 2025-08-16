from pathlib import Path
from typing import Any

from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter
from ask.ui.styles import Styles

IGNORED_PATHS = [
    '.build', '.dart_tool', '.deno', '.env', '.gradle', '.pub-cache', '.tox', '.venv',
    'bin', 'bower_components', '_build', 'build', 'deps', 'dist', 'dist-newstyle',
    'env', 'node_modules', 'obj', 'packages', 'target', 'vendor', 'venv']

def build_tree(path: Path, ignore_patterns: list[str], prefix: str = "") -> str:
    items_to_ignore: set[Path] = set()
    for pattern in ignore_patterns:
        items_to_ignore.update(path.glob(pattern))

    result = f"{prefix}- {path if not prefix else path.name}/\n"  # Show the full path on the top-level directory
    try:
        for item in sorted(path.iterdir()):
            if item.name.startswith('.') or item in items_to_ignore:
                continue
            elif item.is_dir() and item.name not in IGNORED_PATHS:
                result += build_tree(item, ignore_patterns, prefix + "  ")
            else:
                result += f"{prefix}  - {item.name}{'/' if item.is_dir() else ''}\n"
    except PermissionError:
        pass

    return result


class ListTool(Tool):
    name = "List"
    description = load_tool_prompt('list')
    parameters = [
        Parameter("path", "string", "The absolute path of the directory to list (must be absolute, not relative)"),
        Parameter("ignore", "array", "List of glob patterns to ignore", required=False)]

    def render_args(self, args: dict[str, str]) -> str:
        try:
            return str(Path(args['path']).relative_to(Path.cwd()))
        except ValueError:
            return args['path']

    def render_short_response(self, response: str) -> str:
        item_count = response.count('\n') + 1
        return f"Listed {Styles.bold(item_count)} paths"

    def run(self, args: dict[str, Any]) -> str:
        path = Path(args["path"])
        if not path.is_absolute():
            raise ToolError(f"Path '{path}' is not an absolute path. Please provide an absolute path.")
        if not path.exists():
            raise ToolError(f"Path '{path}' does not exist.")
        if not path.is_dir():
            raise ToolError(f"Path '{path}' is not a directory.")

        try:
            return build_tree(path, args.get("ignore", []))
        except PermissionError as e:
            raise ToolError(f"Permission denied for path '{path}'.") from e
        except Exception as e:
            raise ToolError(f"An error occurred while listing directory '{path}': {str(e)}") from e
