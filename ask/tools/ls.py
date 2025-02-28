from pathlib import Path
from typing import Any
from ask.tools.base import Tool, Parameter

class LSTool(Tool):
    name = "ls"
    description = "Lists files and directories in a given path."
    parameters = [Parameter("path", "string", "The absolute path to the directory to list (must be absolute, not relative)")]

    def run(self, args: dict[str, Any]) -> str:
        path = Path(args["path"])
        if not path.is_absolute():
            return f"Error: Path '{path}' is not an absolute path. Please provide an absolute path."
        if not path.exists():
            return f"Error: Path '{path}' does not exist."
        if not path.is_dir():
            return f"Error: Path '{path}' is not a directory."

        try:
            contents = [f"{item.name}/" if item.is_dir() else item.name for item in path.iterdir()]
            return "\n".join(contents) if contents else "Directory is empty."
        except PermissionError:
            return f"Error: Permission denied for path '{path}'."
        except Exception as e:
            return f"Error: {str(e)}"
