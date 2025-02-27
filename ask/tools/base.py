from typing import Any
from dataclasses import dataclass

@dataclass
class Parameter:
    name: str
    type: str
    description: str = ''
    required: bool = True
    enum: list[str] | None = None

class Tool:
    name: str
    description: str
    parameters: list[Parameter]

    @classmethod
    def call(cls, args: dict[str, Any]) -> str:
        for param in cls.parameters:
            if param.required and param.name not in args:
                return f"Error: Missing required parameter: {param.name}"
            if param.name in args and param.enum:
                if args[param.name] not in param.enum:
                    return f"Error: Invalid value for {param.name}. Must be one of: {', '.join(param.enum)}"

        unexpected_args = set(args) - {param.name for param in cls.parameters}
        if unexpected_args:
            return f"Error: Unexpected arguments: {', '.join(unexpected_args)}"

        return cls.run(args)

    @classmethod
    def run(cls, args: dict[str, Any]) -> str:
        raise NotImplementedError("Subclasses should implement this method.")
