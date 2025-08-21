from pathlib import Path
from typing import Any

from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter
from ask.ui.styles import Styles

class WriteTool(Tool):
    name = "Write"
    description = load_tool_prompt('write')
    needs_approval = True
    parameters = [
        Parameter("file_path", "string", "The absolute path to the file to write (must be absolute, not relative)"),
        Parameter("content", "string", "The content to write to the file")]

    def render_args(self, args: dict[str, str]) -> str:
        try:
            return str(Path(args['file_path']).relative_to(Path.cwd()))
        except ValueError:
            return args['file_path']

    def render_short_response(self, response: str) -> str:
        return f"Wrote {Styles.bold('file')}"

    def render_response(self, response: str) -> str:
        return response

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        file_path = Path(args["file_path"])
        if not file_path.is_absolute():
            raise ToolError(f"Path '{file_path}' is not an absolute path. Please provide an absolute path.")
        return {'file_path': file_path, 'content': args['content']}

    async def run(self, file_path: Path, content: str) -> str:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = file_path.exists()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"File {'updated' if file_exists else 'created'} successfully at: {file_path}"
        except PermissionError as e:
            raise ToolError(f"Permission denied for file '{file_path}'.") from e
        except OSError as e:
            raise ToolError(f"Failed to write file '{file_path}': {str(e)}") from e
