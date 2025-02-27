import io
import re
import glob
import mmap
from pathlib import Path
from typing import Any
from ask.tools.base import Tool, Parameter

GREP_TOOL_DESCRIPTION = """
- Fast content search tool that works with any codebase size
- Searches file contents using regular expressions
- Supports full regex syntax (eg. "log.*Error", "function\s+\w+", etc.)
- Filter files by pattern with the include parameter (eg. "*.js", "*.{ts,tsx}")
- Returns matching file paths sorted by modification time
- Use this tool when you need to find files containing specific patterns
""".strip()

PATH_ARG_DESCRIPTION = "The absolute path to the directory to search in (must be absolute, not relative). Defaults to the current working directory."

class GrepTool(Tool):
    name = "grep"
    description = GREP_TOOL_DESCRIPTION
    parameters = [
        Parameter("pattern", "string", "The regular expression pattern to search for in file contents"),
        Parameter("path", "string", PATH_ARG_DESCRIPTION, required=False),
        Parameter("include", "string", "File pattern to include in the search (e.g. \"*.js\", \"*.{ts,tsx}\")", required=False)]

    @classmethod
    def run(cls, args: dict[str, Any]) -> str:
        path = Path(args.get("path", Path.cwd()))
        if not path.is_absolute():
            return f"Error: Path '{path}' is not an absolute path. Please provide an absolute path."
        if not path.exists():
            return f"Error: Path '{path}' does not exist."
        if not path.is_dir():
            return f"Error: Path '{path}' is not a directory."

        try:
            pattern, include = args["pattern"].encode('utf-8'), args.get("include", "**/*")
            regex = re.compile(pattern)
            matches = []
            for file_path in glob.glob(str(path / include), recursive=True):
                if Path(file_path).is_file():
                    try:
                        with io.open(file_path, 'r') as f:
                            if regex.search(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)):
                                matches.append(file_path)
                    except PermissionError:
                        pass
            matches.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
            if matches:
                return f"Found {len(matches)} files\n" + '\n'.join(matches)
            else:
                return "No matches found"
        except re.error as e:
            return f"Error: Invalid regular expression pattern: {str(e)}"
        except PermissionError:
            return f"Error: Permission denied for path '{path}'."
