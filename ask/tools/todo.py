import json
from typing import Any

from ask.prompts import load_tool_prompt
from ask.tools.base import Tool, Parameter, ParameterType
from ask.ui.styles import Colors, Styles, Theme

def parse_response(response: str) -> Any:
    _, todo_list_json = response.split('\n\n', 1)
    return json.loads(todo_list_json)


class ToDoTool(Tool):
    name = "ToDo"
    description = load_tool_prompt('python')
    parameters = [
        Parameter("todos", "The updated todo list", ParameterType.Array([
            Parameter("content", "The todo item content", ParameterType.String),
            Parameter("status", "The status of the todo", ParameterType.Enum(["pending", "in_progress", "completed"])),
        ]))
    ]

    def render_args(self, args: dict[str, Any]) -> str:
        return ''

    def render_short_response(self, args: dict[str, Any], response: str) -> str:
        return self.render_response(args, response)

    def render_response(self, args: dict[str, Any], response: str) -> str:
        lines = []
        for item in parse_response(response):
            if item['status'] == 'pending':
                lines.append(f"☐ {item['content']}")
            elif item['status'] == "in_progress":
                lines.append(f"☐ {Styles.bold(item['content'])}")
            elif item['status'] == "completed":
                lines.append(f"☒ {Colors.hex(Styles.strikethrough(item['content']), Theme.GRAY)}")
        return "\n".join(lines)

    async def run(self, todos: list[dict[str, Any]]) -> str:
        return load_tool_prompt('todo', 'response').format(todo_list_json=json.dumps(todos, indent=2))
