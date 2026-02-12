import difflib
from pathlib import Path
from typing import Any

from ask.messages import Blob, Text
from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter, ParameterType

def get_formatted_lines(lines: list[str], start: int, end: int) -> str:
    return '\n'.join(f'{str(i+1).rjust(6)}→{lines[i]}' for i in range(start, end) if 0 <= i < len(lines))

def read_file(file_path: Path) -> str:
    try:
        with open(file_path, encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise ToolError(f"File '{file_path}' is not a text file or contains invalid Unicode characters.") from e
    except PermissionError as e:
        raise ToolError(f"Permission denied for file '{file_path}'.") from e

def replace(file_path: Path, content: str, old_string: str, new_string: str, replace_all: bool, prefix: str = "") -> str:
    occurrences = content.count(old_string)
    if old_string == new_string:
        raise ToolError(prefix + "old_string and new_string must be different.")
    if occurrences == 0:
        raise ToolError(prefix + f"String '{old_string}' not found in file '{file_path}'.")
    if occurrences > 1 and not replace_all:
        raise ToolError(prefix +
            f"Found {occurrences} matches of the string to replace, but replace_all is false. "
                "To replace all occurrences, set replace_all to true. To replace only one occurrence, "
            f"please provide more context to uniquely identify the instance.\nString: {old_string}")

    return content.replace(old_string, new_string)


class EditTool(Tool):
    name = "Edit"
    description = load_tool_prompt('edit')
    parameters = [
        Parameter("file_path", "The absolute path of the file to modify", ParameterType.String),
        Parameter("old_string", "The text to replace", ParameterType.String),
        Parameter("new_string", "The text to replace it with (must be different from old_string)", ParameterType.String),
        Parameter("replace_all", "Replace all occurrences of old_string (Default: false)", ParameterType.Boolean, required=False)]

    def check(self, args: dict[str, Any]) -> None:
        super().check(args)
        self.check_absolute_path(Path(args["file_path"]), is_file=True)

    def artifacts(self, args: dict[str, Any]) -> dict[str, Any]:
        old_content = read_file(Path(args['file_path']))
        new_content = replace(Path(args['file_path']), old_content, args["old_string"], args["new_string"], args.get("replace_all", False))
        return {'modified': Path(args['file_path']), 'old_content': old_content, 'new_content': new_content}

    def process(self, args: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        old_lines = artifacts['old_content'].splitlines(keepends=True)
        new_lines = artifacts['new_content'].splitlines(keepends=True)
        return {**artifacts, 'diff': list(difflib.unified_diff(old_lines, new_lines, n=3))}

    async def run(self, args: dict[str, Any], artifacts: dict[str, Any]) -> Blob:
        file_path = Path(args['file_path'])
        old_content = artifacts['old_content']
        new_content = artifacts['new_content']

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except PermissionError as e:
            raise ToolError(f"Permission denied when writing to file '{file_path}'.") from e

        if args.get('replace_all', False):
            return Text(f"The file {file_path} has been updated, all occurrences of '{args['old_string']}' have been replaced with '{args['new_string']}'.")
        else:
            lines = new_content.split('\n')
            start_line = old_content[:old_content.find(args['old_string'])].count('\n')
            end_line = start_line + args['old_string'].count('\n') + 1
            if end_line - start_line > 15:
                start_context = get_formatted_lines(lines, start_line - 5, start_line + 5)
                end_context = get_formatted_lines(lines, end_line - 5, end_line + 5)
                context_lines = f"{start_context}\n... [omitted]\n{end_context}"
            else:
                context_lines = get_formatted_lines(lines, start_line - 5, end_line + 5)
            return Text(f"The file {file_path} has been updated. Here's a snippet of the edited file:\n{context_lines}")
