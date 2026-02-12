import json
from typing import Any

from ask.messages import Blob, Text
from ask.prompts import load_tool_prompt
from ask.tools.base import Parameter, ParameterType, Tool


class ToDoTool(Tool):
    name = "ToDo"
    description = load_tool_prompt('python')
    parameters = [
        Parameter("todos", "The updated todo list", ParameterType.Array([
            Parameter("content", "The todo item content", ParameterType.String),
            Parameter("status", "The status of the todo", ParameterType.Enum(["pending", "in_progress", "completed"])),
        ])),
    ]

    async def run(self, args: dict[str, Any], artifacts: dict[str, Any]) -> Blob:
        return Text(load_tool_prompt('todo', 'response').format(todo_list_json=json.dumps(args['todos'], indent=2)))
