from pathlib import Path
from typing import Any

from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter
from ask.ui.styles import Styles

class ReadTool(Tool):
    name = "Read"
    description = load_tool_prompt('read')
    parameters = [
        Parameter("file_path", "string", "The absolute path to the file to read"),
        Parameter("offset", "number", "The line number to start reading from. Only provide if the file is too large to read at once.", required=False),
        Parameter("limit", "number", "The number of lines to read. Only provide if the file is too large to read at once.", required=False)]

    def __init__(self, add_line_numbers: bool = True):
        self.add_line_numbers = add_line_numbers

    def render_args(self, args: dict[str, str]) -> str:
        try:
            return str(Path(args['file_path']).relative_to(Path.cwd()))
        except ValueError:
            return args['file_path']

    def render_short_response(self, response: str) -> str:
        line_count = response.count('\n') + 1
        return f"Read {Styles.bold(line_count)} lines"

    def render_response(self, response: str) -> str:
        return '\n'.join(line.split('→')[-1] for line in response.split('\n'))

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        file_path = Path(args["file_path"])
        if not file_path.is_absolute():
            raise ToolError(f"Path '{file_path}' is not an absolute path. Please provide an absolute path.")
        if not file_path.exists():
            raise ToolError(f"File '{file_path}' does not exist.")
        if not file_path.is_file():
            raise ToolError(f"Path '{file_path}' is not a file.")

        file_path = Path(args["file_path"])
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']
        if file_path.suffix.lower() in image_extensions:
            raise ToolError("Image files not supported yet")

        offset = int(args.get("offset", 0))
        limit = int(args.get("limit", 2000))
        return {'file_path': file_path, 'offset': offset, 'limit': limit}

    async def run(self, file_path: Path, offset: int, limit: int) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i in range(offset):
                    try:
                        next(f)
                    except StopIteration:
                        raise ToolError(f"Offset {offset} is out of bounds, file '{file_path}' only contains {i} lines.") from None

                lines = [f'{str(offset+1).rjust(6)}→'] if self.add_line_numbers else []
                for i, line in enumerate(f):
                    if i >= limit:
                        lines = lines[:-1] + [f"... [truncated, file contains more than {offset + limit} lines]"]
                        break
                    if len(line) > 2000:
                        line = line[:2000] + "... [truncated]\n"
                    lines.append(line)
                    if line.endswith('\n') and self.add_line_numbers:
                        lines.append(f'{str(offset+i+2).rjust(6)}→')

                return ''.join(lines)

        except UnicodeDecodeError as e:
            raise ToolError(f"File '{file_path}' is not a text file or contains invalid Unicode characters.") from e
        except PermissionError as e:
            raise ToolError(f"Permission denied for file '{file_path}'.") from e
