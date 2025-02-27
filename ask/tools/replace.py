from pathlib import Path
from typing import Any
from ask.tools.base import Tool, Parameter

REPLACE_TOOL_DESCRIPTION = """
Write a file to the local filesystem. Overwrites the existing file if there is one.

Before using this tool:

1. Use the ReadFile tool to understand the file's contents and context

2. Directory Verification (only applicable when creating new files):
   - Use the LS tool to verify the parent directory exists and is the correct location
""".strip()

class ReplaceTool(Tool):
    name = "replace"
    description = REPLACE_TOOL_DESCRIPTION
    parameters = [
        Parameter("file_path", "string", "The absolute path to the file to write (must be absolute, not relative)"),
        Parameter("content", "string", "The content to write to the file")]

    @classmethod
    def run(cls, args: dict[str, Any]) -> str:
        file_path = Path(args["file_path"])
        content = args["content"]
        if not file_path.is_absolute():
            return f"Error: File path '{file_path}' is not an absolute path. Please provide an absolute path."
        if not file_path.parent.exists():
            return f"Error: Parent directory '{file_path.parent}' does not exist."

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {file_path}"
        except PermissionError:
            return f"Error: Permission denied for writing to '{file_path}'."
        except OSError as e:
            return f"Error: Failed to write to '{file_path}'."
