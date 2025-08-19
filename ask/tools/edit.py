from pathlib import Path
from typing import Any

from ask.prompts import load_tool_prompt, dedent
from ask.tools.base import ToolError, Tool, Parameter

def get_formatted_lines(lines: list[str], start: int, end: int) -> str:
    return '\n'.join(f'{str(i+1).rjust(6)}→{lines[i]}' for i in range(start, end) if 0 <= i < len(lines))


class EditTool(Tool):
    name = "Edit"
    description = load_tool_prompt('edit')
    parameters = [
        Parameter("file_path", "string", "The absolute path of the file to modify"),
        Parameter("old_string", "string", "The text to replace"),
        Parameter("new_string", "string", "The text to replace it with (must be different from old_string)"),
        Parameter("replace_all", "boolean", "Replace all occurrences of old_string (Default: false)", required=False)]

    def render_args(self, args: dict[str, str]) -> str:
        try:
            return str(Path(args['file_path']).relative_to(Path.cwd()))
        except ValueError:
            return args['file_path']

    def render_short_response(self, response: str) -> str:
        return response

    def render_response(self, response: str) -> str:
        return response

    async def run(self, args: dict[str, Any]) -> str:
        file_path = Path(args["file_path"])
        if not file_path.is_absolute():
            raise ToolError(f"Path '{file_path}' is not an absolute path. Please provide an absolute path.")
        if not file_path.exists():
            raise ToolError(f"File '{file_path}' does not exist.")
        if not file_path.is_file():
            raise ToolError(f"Path '{file_path}' is not a file.")

        old_string = args["old_string"]
        new_string = args["new_string"]
        if old_string == new_string:
            raise ToolError("old_string and new_string must be different.")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError as e:
            raise ToolError(f"File '{file_path}' is not a text file or contains invalid Unicode characters.") from e
        except PermissionError as e:
            raise ToolError(f"Permission denied for file '{file_path}'.") from e

        replace_all = args.get("replace_all", False)
        occurrences = content.count(old_string)
        if occurrences == 0:
            raise ToolError(f"String '{old_string}' not found in file '{file_path}'.")
        if occurrences > 1 and not replace_all:
            raise ToolError(dedent(f"""
                Found {occurrences} matches of the string to replace, but replace_all is false.
                To replace all occurrences, set replace_all to true. To replace only one occurrence,
                please provide more context to uniquely identify the instance.
            """) + f'\nString: {old_string}')

        new_content = content.replace(old_string, new_string)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except PermissionError as e:
            raise ToolError(f"Permission denied when writing to file '{file_path}'.") from e

        if replace_all:
            return f"The file {file_path} has been updated, all occurrences of '{old_string}' have been replaced with '{new_string}'."
        else:
            lines = new_content.split('\n')
            start_line = content[:content.find(old_string)].count('\n')
            end_line = start_line + old_string.count('\n') + 1
            if end_line - start_line > 15:
                start_context = get_formatted_lines(lines, start_line - 5, start_line + 5)
                end_context = get_formatted_lines(lines, end_line - 5, end_line + 5)
                context_lines = f"{start_context}\n... [omitted]\n{end_context}"
            else:
                context_lines = get_formatted_lines(lines, start_line - 5, end_line + 5)
            return f"The file {file_path} has been updated. Here's a snippet of the edited file:\n{context_lines}"
