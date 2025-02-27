from pathlib import Path
from typing import Any
from ask.tools.base import Tool, Parameter

VIEW_TOOL_DESCRIPTION = """
Reads a file from the local filesystem.
The file_path parameter must be an absolute path, not a relative path.
By default, it reads up to 2000 lines starting from the beginning of the file.
You can optionally specify a line offset and limit (especially handy for long files),
but it's recommended to read the whole file by not providing these parameters.
Any lines longer than 2000 characters will be truncated.
""".replace('\n', ' ').strip()

class ViewTool(Tool):
    name = "view"
    description = VIEW_TOOL_DESCRIPTION
    parameters = [
        Parameter("file_path", "string", "The absolute path to the file to read"),
        Parameter("offset", "number", "The line number to start reading from. Only provide if the file is too large to read at once.", required=False),
        Parameter("limit", "number", "The number of lines to read. Only provide if the file is too large to read at once.", required=False)]

    @classmethod
    def run(cls, args: dict[str, Any]) -> str:
        file_path = Path(args["file_path"])
        if not file_path.is_absolute():
            return f"Error: Path '{file_path}' is not an absolute path. Please provide an absolute path."
        if not file_path.exists():
            return f"Error: File '{file_path}' does not exist."
        if not file_path.is_file():
            return f"Error: Path '{file_path}' is not a file."

        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']
        if file_path.suffix.lower() in image_extensions:
            return f"Error: Image files not supported yet"
        if file_path.suffix.lower() == '.ipynb':
            return f"Error: For Jupyter notebooks (.ipynb files), please use the ReadNotebook tool instead."

        offset = int(args.get("offset", 0))
        limit = int(args.get("limit", 2000))

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i in range(offset):
                    try:
                        next(f)
                    except StopIteration:
                        return f"Error: Offset {offset} is out of bounds, file '{file_path}' only contains {i} lines."

                lines = []
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    if len(line) > 2000:
                        line = line[:2000] + "... [truncated]"
                    lines.append(line)

                if not lines:
                    return f"File is empty."
                return ''.join(lines)

        except UnicodeDecodeError:
            return f"Error: File '{file_path}' is not a text file or contains invalid Unicode characters."
        except PermissionError:
            return f"Error: Permission denied for file '{file_path}'."
