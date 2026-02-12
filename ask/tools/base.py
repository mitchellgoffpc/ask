from dataclasses import dataclass
from enum import Enum, member, nonmember
from pathlib import Path
from typing import Any, ClassVar, Union, cast

from ask.messages import Blob

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

class ToolError(Exception): ...

class Tool:
    name: str
    description: str
    parameters: list[Parameter]

    def get_parameter_schema(self, ptype: ParameterType | ParameterType.Enum | ParameterType.Array, description: str) -> dict[str, Any]:
        description_dict = {"description": description} if description else {}
        if isinstance(ptype, ParameterType.Enum):
            return {"type": "string", "enum": ptype.values} | description_dict
        elif isinstance(ptype, ParameterType.Array):
            if isinstance(ptype.items, list):
                items = self.get_parameters_schema(cast(list[Parameter], ptype.items))
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
                    self.check_arguments(item, cast(list[Parameter], ptype.items), prefix=f'{name}[{i}].')
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

    def check(self, args: dict[str, Any]) -> None:
        self.check_arguments(args, self.parameters)

    def artifacts(self, args: dict[str, Any]) -> dict[str, Any]:
        return {}

    def process(self, args: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
        return artifacts

    async def run(self, args: dict[str, Any], artifacts: dict[str, Any]) -> Blob:
        raise NotImplementedError
