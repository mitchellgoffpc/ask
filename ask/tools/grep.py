import glob
import mmap
import re
from pathlib import Path
from typing import Any

from ask.prompts import load_tool_prompt, get_relative_path
from ask.tools.base import ToolError, Tool, Parameter, ParameterType
from ask.ui.core.styles import Styles

def get_content_matches(file_path: Path, content: mmap.mmap, regex: re.Pattern, show_line_nums: bool, before: int, after: int) -> tuple[int, list[str]]:
    if not regex.search(content):
        return 0, []

    text = content[:].decode('utf-8')
    lines = text.splitlines()
    num_matches = 0
    match_groups = []
    for match in regex.finditer(content):
        num_matches += 1
        line_num = text[:match.start()].count('\n')
        start = max(0, line_num - before)
        end = min(len(lines), line_num + after + 1)
        match_groups.append((start, end))

    # Merge overlapping ranges and collect lines
    merged_groups = []
    current_start, current_end = match_groups[0]
    for start, end in match_groups[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            merged_groups.append((current_start, current_end))
            current_start, current_end = start, end
    merged_groups.append((current_start, current_end))

    # Build result with separators
    result = []
    for start, end in merged_groups:
        for j in range(start, end):
            result.append(f"{file_path}:{f'{j+1}:' if show_line_nums else ''}{lines[j]}")
        if before > 0 or after > 0:
            result.append("--")

    return num_matches, result


class GrepTool(Tool):
    name = "Grep"
    description = load_tool_prompt('grep')
    parameters = [
        Parameter("pattern", "The regular expression pattern to search for in file contents", ParameterType.String),
        Parameter("pathspec",
            "Limit the search to paths matching the given pattern. "
            "Both leading paths match and glob patterns are supported. "
            "Defaults to the current working directory.", ParameterType.String, required=False),
        Parameter("output_mode",
            "Grep supports the following output modes: content, files_with_matches, count.\n"
            "- 'content' shows matching lines (supports -A/-B/-C context, -n line numbers, head_limit).\n"
            "- 'files_with_matches' shows file paths (supports head_limit).\n"
            "- 'count' shows match counts (supports head_limit).\n"
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
        path = get_relative_path(args.get('pathspec', Path.cwd()))
        return f'pattern: "{pattern}", path: "{path}"'

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
        pathspec = args.get("pathspec") or str(Path.cwd())

        try:
            flags = 0
            if args.get("-i", False):
                flags |= re.IGNORECASE
            if args.get("multiline", False):
                flags |= re.MULTILINE | re.DOTALL
            regex = re.compile(args["pattern"].encode('utf-8'), flags)
        except re.error as e:
            raise ToolError(f"Invalid regular expression pattern: {str(e)}") from e

        output_mode = args.get("output_mode", "files_with_matches")
        before = args.get("-B", 0) or args.get("-C", 0)
        after = args.get("-A", 0) or args.get("-C", 0)
        return {
            'pattern': args['pattern'], 'pathspec': pathspec, 'regex': regex, 'output_mode': output_mode,
            'head_limit': args.get("head_limit"), 'show_line_nums': args.get("-n", False), 'before': before, 'after': after}

    async def run(self, pattern: str, pathspec: str, regex: re.Pattern, output_mode: str,
                        head_limit: int | None, show_line_nums: bool, before: int, after: int) -> str:
        try:
            # Collect all files to search
            files_to_search = []
            for path in glob.glob(pathspec, recursive=True):
                match_path = Path(path)
                if match_path.is_file():
                    files_to_search.append(match_path)
                elif match_path.is_dir():
                    for file_path in match_path.rglob('*'):
                        if file_path.is_file():
                            files_to_search.append(file_path)

            # Search each file
            results = []
            total_matches = 0
            for file_path in files_to_search:
                try:
                    with open(file_path, 'rb') as f:
                        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as content:
                            if output_mode == "content":
                                num_matches, lines = get_content_matches(file_path, content, regex, show_line_nums, before, after)
                                results.extend(lines)
                                total_matches += num_matches
                            elif output_mode == "count":
                                if (num_matches := len(regex.findall(content))) > 0:
                                    results.append(f"{file_path}:{num_matches}")
                                    total_matches += 1
                            else:
                                if regex.search(content):
                                    results.append(str(file_path))
                                    total_matches += 1
                except (PermissionError, UnicodeDecodeError, OSError, ValueError):
                    pass

            if output_mode == "files_with_matches":
                results.sort(key=lambda x: Path(x).stat().st_mtime, reverse=True)
            if results and results[-1] == "--":
                results.pop()
            if head_limit:
                results = results[:head_limit]
            if results:
                return f"Found {total_matches} {'matches' if output_mode == 'content' else 'files'}\n" + '\n'.join(results)
            else:
                return "No matches found"
        except PermissionError as e:
            raise ToolError(f"Permission denied for path '{pathspec}'.") from e
        except Exception as e:
            raise ToolError(f"An error occurred while searching in '{pathspec}': {str(e)}") from e
