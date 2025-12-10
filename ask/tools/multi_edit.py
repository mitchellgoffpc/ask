import difflib
from pathlib import Path
from typing import Any

from ask.models.base import Blob, Text
from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Parameter, ParameterType
from ask.tools.edit import EditTool, read_file, replace, get_formatted_lines


class MultiEditTool(EditTool):
    name = "MultiEdit"
    description = load_tool_prompt('multi_edit')
    parameters = [
        Parameter("file_path", "The absolute path to the file to modify", ParameterType.String),
        Parameter("edits", "Array of edit operations to perform sequentially on the file", ParameterType.Array(min_items=1, items=[
            Parameter("old_string", "The text to replace", ParameterType.String),
            Parameter("new_string", "The text to replace it with", ParameterType.String),
            Parameter("replace_all", "Replace all occurences of old_string (default false).", ParameterType.Boolean, required=False)
        ]))
    ]

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super(EditTool, self).check(args)
        file_path = Path(args["file_path"])
        self.check_absolute_path(file_path, is_file=True)

        content = working_content = read_file(file_path)
        for i, edit in enumerate(args['edits']):
            replace_all = edit.get("replace_all", False)
            working_content = replace(file_path, working_content, edit['old_string'], edit["new_string"], replace_all, prefix=f"Edit {i+1}: ")

        old_lines = content.splitlines(keepends=True)
        new_lines = working_content.splitlines(keepends=True)
        diff = list(difflib.unified_diff(old_lines, new_lines, n=3))
        return {'file_path': file_path, 'old_content': content, 'new_content': working_content, 'diff': diff, 'edits': args['edits']}

    async def run(self, file_path: Path, old_content: str, new_content: str, diff: list[str], edits: list[dict[str, Any]]) -> Blob:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except PermissionError as e:
            raise ToolError(f"Permission denied when writing to file '{file_path}'.") from e

        edit_count = len(edits)
        lines = new_content.split('\n')

        # Find the range of changes for context
        if old_content:
            first_edit = edits[0]
            first_old_pos = old_content.find(first_edit["old_string"])
            if first_old_pos != -1:
                start_line = old_content[:first_old_pos].count('\n')
                end_line = start_line + max(edit["old_string"].count('\n') + 1 for edit in edits)
                context_lines = get_formatted_lines(lines, max(0, start_line - 3), min(len(lines), end_line + 3))
                return Text(
                    f"The file {file_path} has been updated with {edit_count} edit{'s' if edit_count > 1 else ''}. "
                    f"Here's a snippet of the edited file:\n{context_lines}")

        return Text(f"The file {file_path} has been updated with {edit_count} edit{'s' if edit_count > 1 else ''}.")
