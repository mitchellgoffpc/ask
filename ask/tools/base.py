from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, member, nonmember
from pathlib import Path
from typing import Any, Callable, ClassVar, Coroutine, Union

from ask.models.base import Blob
from ask.ui.core.styles import Colors, Theme

def abbreviate(text: str, max_lines: int) -> str:
    lines = text.strip().split('\n')
    if len(lines) <= max_lines:
        return text.strip()
    abbreviated = '\n'.join(lines[:max_lines])
    expand_text = Colors.hex(f"… +{len(lines) - max_lines} lines (ctrl+r to expand)", Theme.GRAY)
    return f"{abbreviated}\n{expand_text}"


# Parameter definitions

class ParameterType(Enum):
    @nonmember
    @dataclass
    class Enum:
        value: ClassVar[str] = 'enum'
        values: list[str]

    @nonmember
    @dataclass
    class Array:
        value: ClassVar[str] = 'array'
        items: Union['ParameterType', 'ParameterType.Enum', 'ParameterType.Array', list['Parameter']]
        min_items: int = 0

    String = 'string'
    Number = 'number'
    Boolean = 'boolean'
    Enum_ = member(Enum)
    Array_ = member(Array)

@dataclass
class Parameter:
    name: str
    description: str
    type: ParameterType | ParameterType.Enum | ParameterType.Array
    required: bool = True


# Tool base class

class ToolCallStatus(Enum):
    PENDING = 'pending'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'

class ToolError(Exception): ...

class Tool(metaclass=ABCMeta):
    name: str
    description: str
    parameters: list[Parameter]
    run: Callable[..., Coroutine[Any, Any, 'Blob']]

    def get_parameter_schema(self, ptype: ParameterType | ParameterType.Enum | ParameterType.Array, description: str) -> dict[str, Any]:
        description_dict = {"description": description} if description else {}
        if isinstance(ptype, ParameterType.Enum):
            return {"type": "string", "enum": ptype.values} | description_dict
        elif isinstance(ptype, ParameterType.Array):
            if isinstance(ptype.items, list):
                items = self.get_parameters_schema(ptype.items)
            else:
                items = self.get_parameter_schema(ptype.items, "")
            return {"type": "array", "minItems": ptype.min_items, "items": items} | description_dict
        else:
            return {"type": ptype.value} | description_dict

    def get_parameters_schema(self, parameters: list[Parameter]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {p.name: self.get_parameter_schema(p.type, p.description) for p in parameters},
            "required": [p.name for p in parameters if p.required]}

    def get_input_schema(self) -> dict[str, Any]:
        return self.get_parameters_schema(self.parameters)

    def render_name(self) -> str:
        return self.name

    @abstractmethod
    def render_args(self, args: dict[str, Any]) -> str: ...

    @abstractmethod
    def render_short_response(self, args: dict[str, Any], response: str) -> str: ...

    def render_response(self, args: dict[str, Any], response: str) -> str:
        return response

    def render_image_response(self, args: dict[str, Any], response: bytes) -> str:
        raise NotImplementedError("Image response not implemented")

    def render_pdf_response(self, args: dict[str, Any], response: str) -> str:
        raise NotImplementedError("PDF response not implemented")

    def render_error(self, error: str) -> str:
        return f"Error: {error}"

    def check_absolute_path(self, path: Path, is_file: bool = False) -> None:
        if not path.is_absolute():
            raise ToolError(f"Path '{path}' is not an absolute path. Please provide an absolute path.")
        if not path.exists():
            raise ToolError(f"File '{path}' does not exist.")
        if is_file and not path.is_file():
            raise ToolError(f"Path '{path}' is not a file.")
        elif not is_file and not path.is_dir():
            raise ToolError(f"Path '{path}' is not a directory.")

    def check_argument(self, name: str, value: Any, ptype: ParameterType | ParameterType.Enum | ParameterType.Array) -> None:
        if ptype is ParameterType.String and not isinstance(value, str):
            raise ToolError(f"Parameter '{name}' must be a string")
        elif ptype is ParameterType.Number and not isinstance(value, (int, float)):
            raise ToolError(f"Parameter '{name}' must be a number")
        elif ptype is ParameterType.Boolean and not isinstance(value, bool):
            raise ToolError(f"Parameter '{name}' must be a boolean")
        elif isinstance(ptype, ParameterType.Enum):
            if not isinstance(value, str):
                raise ToolError(f"Parameter '{name}' must be a string")
            if value not in ptype.values:
                raise ToolError(f"Invalid value for '{name}'. Must be one of: {', '.join(ptype.values)}")
        elif isinstance(ptype, ParameterType.Array):
            if not isinstance(value, list):
                raise ToolError(f"Parameter '{name}' must be an array")
            if len(value) < ptype.min_items:
                raise ToolError(f"Parameter '{name}' must have at least {ptype.min_items} items")
            if isinstance(ptype.items, list):
                for i, item in enumerate(value):
                    if not isinstance(item, dict):
                        raise ToolError(f"Parameter '{name}[{i}]' must be an object")
                    self.check_arguments(item, ptype.items, prefix=f'{name}[{i}].')
            else:
                for i, item in enumerate(value):
                    self.check_argument(f'{name}[{i}]', item, ptype.items)

    def check_arguments(self, args: dict[str, Any], parameters: list[Parameter], prefix: str = '') -> None:
        for param in parameters:
            if param.required and param.name not in args:
                raise ToolError(f"Missing required parameter: {prefix}{param.name}")
            if param.name in args:
                self.check_argument(f'{prefix}{param.name}', args[param.name], param.type)
        unexpected_args = set(args) - {param.name for param in parameters}
        if unexpected_args:
            raise ToolError(f"Unexpected arguments: {prefix}{', '.join(unexpected_args)}")

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        self.check_arguments(args, self.parameters)
        return args
