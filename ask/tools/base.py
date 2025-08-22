from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

class ToolError(Exception): ...

@dataclass
class Parameter:
    name: str
    type: str
    description: str = ''
    required: bool = True
    enum: list[str] | None = None

class Tool(metaclass=ABCMeta):
    name: str
    description: str
    parameters: list[Parameter]
    run: Callable[..., Any]

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {p.name: {"type": p.type, "description": p.description} for p in self.parameters},
            "required": [p.name for p in self.parameters if p.required],
            "additionalProperties": False,
            "$schema": "http://json-schema.org/draft-07/schema#",
        }

    @abstractmethod
    def render_args(self, args: dict[str, Any]) -> str: ...

    @abstractmethod
    def render_short_response(self, response: str) -> str: ...

    def render_response(self, response: str) -> str:
        return response

    def render_error(self, error: str) -> str:
        return f"Error: {error}"

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        for param in self.parameters:
            if param.required and param.name not in args:
                raise ToolError(f"Missing required parameter: {param.name}")
            if param.name in args and param.enum:
                if args[param.name] not in param.enum:
                    raise ToolError(f"Invalid value for {param.name}. Must be one of: {', '.join(param.enum)}")

        unexpected_args = set(args) - {param.name for param in self.parameters}
        if unexpected_args:
            raise ToolError(f"Unexpected arguments: {', '.join(unexpected_args)}")

        return args
