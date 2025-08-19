import io
import re
import glob
import mmap
from pathlib import Path
from typing import Any

from ask.prompts import dedent, load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter
from ask.ui.styles import Styles

class GrepTool(Tool):
    name = "Grep"
    description = load_tool_prompt('grep')
    parameters = [
        Parameter("pattern", "string", 'The regular expression pattern to search for in file contents'),
        Parameter("path", "string", 'File or directory to search in (rg PATH). Defaults to current working directory.', required=False),
        Parameter("glob", "string", 'Glob pattern to filter files (e.g. "*.js", "*.{ts,tsx}") - maps to rg --glob', required=False),
        Parameter("output_mode", "string", dedent("""
            Output mode: "content" shows matching lines (supports -A/-B/-C context, -n line numbers, head_limit),
            "files_with_matches" shows file paths (supports head_limit), "count" shows match counts (supports head_limit).
            Defaults to "files_with_matches"."""), required=False),
        Parameter("-B", "number", 'Number of lines to show before each match (rg -B). Requires output_mode: "content", ignored otherwise.', required=False),
        Parameter("-A", "number", 'Number of lines to show after each match (rg -A). Requires output_mode: "content", ignored otherwise.', required=False),
        Parameter("-C", "number", dedent("""
            Number of lines to show before and after each match (rg -C). Requires output_mode: "content", ignored otherwise."""), required=False),
        Parameter("-n", "boolean", 'Show line numbers in output (rg -n). Requires output_mode: "content", ignored otherwise.', required=False),
        Parameter("-i", "boolean", 'Case insensitive search (rg -i)', required=False),
        Parameter("head_limit", "number", dedent("""
            Limit output to first N lines/entries, equivalent to "| head -N".
            Works across all output modes: content (limits output lines), files_with_matches (limits file paths), count (limits count entries).
            When unspecified, shows all results from ripgrep."""), required=False),
        Parameter("multiline", "boolean", dedent("""
            Enable multiline mode where . matches newlines and patterns can span lines (rg -U --multiline-dotall). Default: false."""), required=False)
    ]

    def render_args(self, args: dict[str, str]) -> str:
        pattern = args.get('pattern', '')
        if len(pattern) > 50:
            pattern = pattern[:47] + "..."
        try:
            path = str(Path(args['path']).relative_to(Path.cwd()))
        except ValueError:
            path = args['path']
        return f'pattern: "{pattern}", path: "{path}", output_mode: "{args["output_mode"]}"'

    def render_short_response(self, response: str) -> str:
        if response.startswith("Found "):
            match_count = response.split()[1]
            return f"Found {Styles.bold(match_count)} matches"
        elif "No matches found" in response:
            return "No matches found"
        else:
            return "Search completed"

    async def run(self, args: dict[str, Any]) -> str:
        path = Path(args.get("path", Path.cwd()))
        if not path.is_absolute():
            raise ToolError(f"Path '{path}' is not an absolute path. Please provide an absolute path.")
        if not path.exists():
            raise ToolError(f"Path '{path}' does not exist.")
        if not path.is_dir():
            raise ToolError(f"Path '{path}' is not a directory.")

        try:
            pattern = args["pattern"].encode('utf-8')
            flags = 0
            if args.get("-i", False):
                flags |= re.IGNORECASE
            if args.get("multiline", False):
                flags |= re.MULTILINE | re.DOTALL
            regex = re.compile(pattern, flags)
            matches = []
            for file_path in glob.glob(str(path / args.get("glob", "**/*")), recursive=True):
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
            raise ToolError(f"Invalid regular expression pattern: {str(e)}") from e
        except PermissionError as e:
            raise ToolError(f"Permission denied for path '{path}'.") from e
        except Exception as e:
            raise ToolError(f"An error occurred while searching in '{path}': {str(e)}") from e
