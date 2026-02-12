import unittest
from typing import Any

import pytest

from ask.tools.base import Parameter, ParameterType, Tool, ToolError


class DummyTool(Tool):
    def __init__(self, parameters: list[Parameter]) -> None:
        self.name = "test"
        self.description = "test tool"
        self.parameters = parameters

    def render_args(self, args: dict[str, Any]) -> str: return ""
    def render_short_response(self, args: dict[str, Any], response: str) -> str: return ""


class TestParameterValidation(unittest.TestCase):
    def test_string_parameter(self) -> None:
        tool = DummyTool([Parameter("text", "string param", ParameterType.String)])
        tool.check({"text": "hello"})
        with pytest.raises(ToolError) as context:
            tool.check({"text": 123})
        assert str(context.value) == "Parameter 'text' must be a string"

    def test_number_parameter(self) -> None:
        tool = DummyTool([Parameter("num", "number param", ParameterType.Number)])
        tool.check({"num": 42})
        tool.check({"num": 3.14})
        with pytest.raises(ToolError) as context:
            tool.check({"num": "not a number"})
        assert str(context.value) == "Parameter 'num' must be a number"

    def test_boolean_parameter(self) -> None:
        tool = DummyTool([Parameter("flag", "boolean param", ParameterType.Boolean)])
        tool.check({"flag": True})
        tool.check({"flag": False})
        with pytest.raises(ToolError) as context:
            tool.check({"flag": "true"})
        assert str(context.value) == "Parameter 'flag' must be a boolean"

    def test_enum_parameter(self) -> None:
        tool = DummyTool([Parameter("color", "enum param", ParameterType.Enum(["red", "green", "blue"]))])
        tool.check({"color": "red"})
        with pytest.raises(ToolError) as context:
            tool.check({"color": "yellow"})
        assert str(context.value) == "Invalid value for 'color'. Must be one of: red, green, blue"
        with pytest.raises(ToolError) as context:
            tool.check({"color": 1})
        assert str(context.value) == "Parameter 'color' must be a string"

    def test_string_array_parameter(self) -> None:
        tool = DummyTool([Parameter("items", "array param", ParameterType.Array(ParameterType.String, min_items=1))])
        tool.check({"items": ["a", "b"]})
        with pytest.raises(ToolError) as context:
            tool.check({"items": []})
        assert str(context.value) == "Parameter 'items' must have at least 1 items"
        with pytest.raises(ToolError) as context:
            tool.check({"items": "not an array"})
        assert str(context.value) == "Parameter 'items' must be an array"
        with pytest.raises(ToolError) as context:
            tool.check({"items": ["a", 1]})
        assert str(context.value) == "Parameter 'items[1]' must be a string"

    def test_object_array_parameter(self) -> None:
        tool = DummyTool([Parameter("items", "array param", ParameterType.Array([Parameter("text", "string param", ParameterType.String)]))])
        tool.check({"items": [{"text": "a"}, {"text": "b"}]})
        with pytest.raises(ToolError) as context:
            tool.check({"items": [{"text": "a"}, 1]})
        assert str(context.value) == "Parameter 'items[1]' must be an object"
        with pytest.raises(ToolError) as context:
            tool.check({"items": [{"text": 1}]})
        assert str(context.value) == "Parameter 'items[0].text' must be a string"
        with pytest.raises(ToolError) as context:
            tool.check({"items": [{"text": "a"}, {}]})
        assert str(context.value) == "Missing required parameter: items[1].text"
        with pytest.raises(ToolError) as context:
            tool.check({"items": [{"text": "a", "extra": "extra"}]})
        assert str(context.value) == "Unexpected arguments: items[0].extra"

    def test_mismatched_parameters(self) -> None:
        tool = DummyTool([Parameter("required", "required param", ParameterType.String)])
        with pytest.raises(ToolError) as context:
            tool.check({})
        assert str(context.value) == "Missing required parameter: required"
        with pytest.raises(ToolError) as context:
            tool.check({"required": "value", "extra": "extra"})
        assert str(context.value) == "Unexpected arguments: extra"
