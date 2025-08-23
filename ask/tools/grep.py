import io
import re
import glob
import mmap
from pathlib import Path
from typing import Any

from ask.prompts import load_tool_prompt, get_relative_path
from ask.tools.base import ToolError, Tool, Parameter, ParameterType
from ask.ui.styles import Styles

class GrepTool(Tool):
    name = "Grep"
    description = load_tool_prompt('grep')
    parameters = [
        Parameter("pattern", "The regular expression pattern to search for in file contents", ParameterType.String),
        Parameter("path", "File or directory to search in (rg PATH). Defaults to current working directory.", ParameterType.String, required=False),
        Parameter("glob", 'Glob pattern to filter files (e.g. "*.js", "*.{ts,tsx}") - maps to rg --glob', ParameterType.String, required=False),
        Parameter("output_mode",
            'Output mode: "content" shows matching lines (supports -A/-B/-C context, -n line numbers, head_limit), '
            '"files_with_matches" shows file paths (supports head_limit), "count" shows match counts (supports head_limit). '
            'Defaults to "files_with_matches".', ParameterType.String, required=False),
        Parameter("-B", 'Number of lines to show before each match (rg -B). Requires output_mode: "content", ignored otherwise.',
            ParameterType.Number, required=False),
        Parameter("-A", 'Number of lines to show after each match (rg -A). Requires output_mode: "content", ignored otherwise.',
            ParameterType.Number, required=False),
        Parameter("-C", 'Number of lines to show before and after each match (rg -C). Requires output_mode: "content", ignored otherwise.',
            ParameterType.Number, required=False),
        Parameter("-n", 'Show line numbers in output (rg -n). Requires output_mode: "content", ignored otherwise.', ParameterType.Boolean, required=False),
        Parameter("-i", "Case insensitive search (rg -i)", ParameterType.Boolean, required=False),
        Parameter("head_limit",
            'Limit output to first N lines/entries, equivalent to "| head -N". '
            'Works across all output modes: content (limits output lines), files_with_matches (limits file paths), count (limits count entries). '
            'When unspecified, shows all results from ripgrep.', ParameterType.Number, required=False),
        Parameter("multiline", 'Enable multiline mode where . matches newlines and patterns can span lines (rg -U --multiline-dotall). Default: false.',
            ParameterType.Boolean, required=False)
    ]

    def render_args(self, args: dict[str, str]) -> str:
        pattern = args.get('pattern', '')
        if len(pattern) > 50:
            pattern = pattern[:47] + "..."
        path = get_relative_path(args['path'])
        return f'pattern: "{pattern}", path: "{path}", output_mode: "{args["output_mode"]}"'

    def render_short_response(self, args: dict[str, Any], response: str) -> str:
        if response.startswith("Found "):
            match_count = response.split()[1]
            return f"Found {Styles.bold(match_count)} matches"
        elif "No matches found" in response:
            return "No matches found"
        else:
            return "Search completed"

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        path = Path(args.get("path", Path.cwd()))
        self.check_absolute_path(path, is_file=False)

        try:
            flags = 0
            if args.get("-i", False):
                flags |= re.IGNORECASE
            if args.get("multiline", False):
                flags |= re.MULTILINE | re.DOTALL
            regex = re.compile(args["pattern"].encode('utf-8'), flags)
        except re.error as e:
            raise ToolError(f"Invalid regular expression pattern: {str(e)}") from e

        glob_pattern = args.get("glob", "**/*")
        return {'path': path, 'glob_pattern': glob_pattern, 'regex': regex}

    async def run(self, path: Path, glob_pattern: str, regex: re.Pattern) -> str:
        try:
            matches = []
            for file_path in glob.glob(str(path / glob_pattern), recursive=True):
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
        except PermissionError as e:
            raise ToolError(f"Permission denied for path '{path}'.") from e
        except Exception as e:
            raise ToolError(f"An error occurred while searching in '{path}': {str(e)}") from e
