from pathlib import Path
from typing import Any

from ask.models.base import Blob, Text, Image, PDF
from ask.prompts import load_tool_prompt, get_relative_path
from ask.tools.base import ToolError, Tool, Parameter, ParameterType
from ask.ui.core.styles import Styles

IMAGE_MIME_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}

def read_text(file_path: Path, offset: int, max_lines: int | None, max_cols: int | None, add_line_numbers: bool) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        for i in range(offset):
            try:
                next(f)
            except StopIteration:
                raise ValueError(f"Offset {offset} is out of bounds, file '{file_path}' only contains {i} lines.") from None

        lines = [f'{str(offset+1).rjust(6)}→'] if add_line_numbers else []
        for i, line in enumerate(f):
            if max_lines and i >= max_lines:
                lines = lines[:-1] + [f"... [truncated, file contains more than {offset + max_lines} lines]"]
                break
            if max_cols and len(line) > max_cols:
                line = line[:max_cols] + "... [truncated]\n"
            lines.append(line)
            if line.endswith('\n') and add_line_numbers:
                lines.append(f'{str(offset+i+2).rjust(6)}→')

        return ''.join(lines)

def read_bytes(file_path: Path) -> bytes:
    with open(file_path, 'rb') as f:
        return f.read()

def read_file(file_path: Path, offset: int = 0, max_lines: int | None = None, max_cols: int | None = None, add_line_numbers: bool = True) -> Blob:
    file_extension = file_path.suffix.lower().removeprefix('.')
    if file_extension in IMAGE_MIME_TYPES:
        return Image(data=read_bytes(file_path), mimetype=IMAGE_MIME_TYPES[file_extension])
    elif file_extension == 'pdf':
        return PDF(name=file_path.name, data=read_bytes(file_path))
    else:
        return Text(read_text(file_path, offset, max_lines, max_cols, add_line_numbers))


class ReadTool(Tool):
    name = "Read"
    description = load_tool_prompt('read')
    parameters = [
        Parameter("file_path", "The absolute path to the file to read", ParameterType.String),
        Parameter("offset", "The line number to start reading from. Only provide if the file is too large to read at once.",
            ParameterType.Number, required=False),
        Parameter("limit", "The number of lines to read. Only provide if the file is too large to read at once.", ParameterType.Number, required=False)]

    def __init__(self, add_line_numbers: bool = True):
        self.add_line_numbers = add_line_numbers

    def render_args(self, args: dict[str, str]) -> str:
        return get_relative_path(args['file_path'])

    def render_short_response(self, args: dict[str, Any], response: str) -> str:
        line_count = response.count('\n') + 1
        return f"Read {Styles.bold(line_count)} lines"

    def render_response(self, args: dict[str, Any], response: str) -> str:
        return '\n'.join(line.split('→')[-1] for line in response.split('\n'))

    def render_image_response(self, args: dict[str, Any], response: bytes) -> str:
        return "Read image"

    def render_pdf_response(self, args: dict[str, Any], response: str) -> str:
        return "Read PDF"

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        file_path = Path(args["file_path"])
        self.check_absolute_path(file_path, is_file=True)

        offset = int(args.get("offset", 0))
        limit = int(args.get("limit", 2000))
        return {'file_path': file_path, 'offset': offset, 'limit': limit}

    async def run(self, file_path: Path, offset: int, limit: int) -> Blob:
        try:
            return read_file(file_path, offset, max_lines=limit, max_cols=2000, add_line_numbers=self.add_line_numbers)
        except UnicodeDecodeError as e:
            raise ToolError(f"File '{file_path}' is not a text file or contains invalid Unicode characters.") from e
        except PermissionError as e:
            raise ToolError(f"Permission denied for file '{file_path}'.") from e
