from pathlib import Path
from typing import Any

from ask.messages import Blob, Text
from ask.prompts import load_tool_prompt
from ask.tools.base import Parameter, ParameterType, ToolError
from ask.tools.edit import EditTool, get_formatted_lines, read_file, replace


class MultiEditTool(EditTool):
    name = "MultiEdit"
    description = load_tool_prompt('multi_edit')
    parameters = [
        Parameter("file_path", "The absolute path to the file to modify", ParameterType.String),
        Parameter("edits", "Array of edit operations to perform sequentially on the file", ParameterType.Array(min_items=1, items=[
            Parameter("old_string", "The text to replace", ParameterType.String),
            Parameter("new_string", "The text to replace it with", ParameterType.String),
            Parameter("replace_all", "Replace all occurences of old_string (default false).", ParameterType.Boolean, required=False),
        ])),
    ]

    def artifacts(self, args: dict[str, Any]) -> dict[str, Any]:
        file_path = Path(args['file_path'])
        old_content = working_content = read_file(file_path)
        for i, edit in enumerate(args['edits']):
            replace_all = edit.get("replace_all", False)
            working_content = replace(file_path, working_content, edit['old_string'], edit["new_string"], replace_all, prefix=f"Edit {i+1}: ")
        return {'modified': file_path, 'old_content': old_content, 'new_content': working_content}

    async def run(self, args: dict[str, Any], artifacts: dict[str, Any]) -> Blob:
        file_path = Path(args['file_path'])
        old_content = artifacts['old_content']
        new_content = artifacts['new_content']
        edits = args['edits']

        try:
            with file_path.open('w', encoding='utf-8') as f:
                f.write(new_content)
        except PermissionError as e:
            raise ToolError(f"Permission denied when writing to file '{file_path}'.") from e

        edit_count = len(edits)
        lines = new_content.split('\n')

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
