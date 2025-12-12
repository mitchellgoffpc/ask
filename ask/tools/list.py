from pathlib import Path
from typing import Any

from ask.models.base import Blob, Text
from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter, ParameterType

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
        Parameter("path", "The absolute path of the directory to list (must be absolute, not relative)", ParameterType.String),
        Parameter("ignore", "List of glob patterns to ignore", ParameterType.Array(ParameterType.String), required=False)]

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        self.check_absolute_path(Path(args['path']), is_file=False)
        return {'path': Path(args["path"]), 'ignore': args.get("ignore", [])}

    async def run(self, path: Path, ignore: list[str]) -> Blob:
        try:
            return Text(build_tree(path, ignore))
        except PermissionError as e:
            raise ToolError(f"Permission denied for path '{path}'.") from e
        except Exception as e:
            raise ToolError(f"An error occurred while listing directory '{path}': {str(e)}") from e
