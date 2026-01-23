from pathlib import Path
from typing import Any

from ask.messages import Blob, Text
from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Parameter, ParameterType
from ask.tools.edit import EditTool

class WriteTool(EditTool):
    name = "Write"
    description = load_tool_prompt('write')
    parameters = [
        Parameter("file_path", "The absolute path to the file to write (must be absolute, not relative)", ParameterType.String),
        Parameter("content", "The content to write to the file", ParameterType.String)]

    def check(self, args: dict[str, Any]) -> None:
        super(EditTool, self).check(args)
        if not (path := Path(args["file_path"])).is_absolute():
            raise ToolError(f"Path '{path}' is not an absolute path. Please provide an absolute path.")

    def artifacts(self, args: dict[str, Any]) -> dict[str, Any]:
        file_path = Path(args["file_path"])
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

        return {'old_content': old_content, 'new_content': new_content}

    async def run(self, args: dict[str, Any], artifacts: dict[str, Any]) -> Blob:
        file_path = Path(args['file_path'])
        new_content = artifacts['new_content']

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = file_path.exists()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return Text(f"File {'updated' if file_exists else 'created'} successfully at: {file_path}")
        except PermissionError as e:
            raise ToolError(f"Permission denied for file '{file_path}'.") from e
        except OSError as e:
            raise ToolError(f"Failed to write file '{file_path}': {str(e)}") from e
