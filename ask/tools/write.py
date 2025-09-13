import difflib
from pathlib import Path
from typing import Any

from ask.prompts import load_tool_prompt, get_relative_path
from ask.tools.base import ToolError, Tool, Parameter, ParameterType, abbreviate
from ask.ui.styles import Styles
from ask.ui.markdown_ import highlight_code

class WriteTool(Tool):
    name = "Write"
    description = load_tool_prompt('write')
    parameters = [
        Parameter("file_path", "The absolute path to the file to write (must be absolute, not relative)", ParameterType.String),
        Parameter("content", "The content to write to the file", ParameterType.String)]

    def render_args(self, args: dict[str, str]) -> str:
        return get_relative_path(args['file_path'])

    def render_short_response(self, args: dict[str, Any], response: str) -> str:
        return abbreviate(self.render_response(args, response), max_lines=8)

    def render_response(self, args: dict[str, Any], response: str) -> str:
        num_lines = args['new_content'].count('\n') + 1
        status_line = f"Wrote {Styles.bold(str(num_lines))} lines to {Styles.bold(get_relative_path(args['file_path']))}"
        return f"{status_line}\n{highlight_code(response, '')}"

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        file_path = Path(args["file_path"])
        if not file_path.is_absolute():
            raise ToolError(f"Path '{file_path}' is not an absolute path. Please provide an absolute path.")

        new_content = args['content']
        old_content = ""
        if file_path.exists():
            if not file_path.is_file():
                raise ToolError(f"Path '{file_path}' exists but is not a file.")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            except UnicodeDecodeError as e:
                raise ToolError(f"File '{file_path}' is not a text file or contains invalid Unicode characters.") from e
            except PermissionError as e:
                raise ToolError(f"Permission denied for file '{file_path}'.") from e

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = list(difflib.unified_diff(old_lines, new_lines, n=3))
        return {'file_path': file_path, 'old_content': old_content, 'new_content': new_content, 'diff': diff}

    async def run(self, file_path: Path, old_content: str, new_content: str, diff: list[str]) -> str:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = file_path.exists()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return f"File {'updated' if file_exists else 'created'} successfully at: {file_path}"
        except PermissionError as e:
            raise ToolError(f"Permission denied for file '{file_path}'.") from e
        except OSError as e:
            raise ToolError(f"Failed to write file '{file_path}': {str(e)}") from e
