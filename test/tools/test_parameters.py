import unittest
from typing import Any

from ask.tools.base import Tool, Parameter, ParameterType, ToolError

class DummyTool(Tool):
    def __init__(self, parameters: list[Parameter]):
        self.name = "test"
        self.description = "test tool"
        self.parameters = parameters

    def render_args(self, args: dict[str, Any]) -> str: return ""
    def render_short_response(self, args: dict[str, Any], response: str) -> str: return ""


class TestParameterValidation(unittest.TestCase):
    def test_string_parameter(self):
        tool = DummyTool([Parameter("text", "string param", ParameterType.String)])
        tool.check({"text": "hello"})
        with self.assertRaises(ToolError) as context:
            tool.check({"text": 123})
        self.assertEqual(str(context.exception), "Parameter 'text' must be a string")

    def test_number_parameter(self):
        tool = DummyTool([Parameter("num", "number param", ParameterType.Number)])
        tool.check({"num": 42})
        tool.check({"num": 3.14})
        with self.assertRaises(ToolError) as context:
            tool.check({"num": "not a number"})
        self.assertEqual(str(context.exception), "Parameter 'num' must be a number")

    def test_boolean_parameter(self):
        tool = DummyTool([Parameter("flag", "boolean param", ParameterType.Boolean)])
        tool.check({"flag": True})
        tool.check({"flag": False})
        with self.assertRaises(ToolError) as context:
            tool.check({"flag": "true"})
        self.assertEqual(str(context.exception), "Parameter 'flag' must be a boolean")

    def test_enum_parameter(self):
        tool = DummyTool([Parameter("color", "enum param", ParameterType.Enum(["red", "green", "blue"]))])
        tool.check({"color": "red"})
        with self.assertRaises(ToolError) as context:
            tool.check({"color": "yellow"})
        self.assertEqual(str(context.exception), "Invalid value for 'color'. Must be one of: red, green, blue")
        with self.assertRaises(ToolError) as context:
            tool.check({"color": 1})
        self.assertEqual(str(context.exception), "Parameter 'color' must be a string")

    def test_string_array_parameter(self):
        tool = DummyTool([Parameter("items", "array param", ParameterType.Array(ParameterType.String, min_items=1))])
        tool.check({"items": ["a", "b"]})
        with self.assertRaises(ToolError) as context:
            tool.check({"items": []})
        self.assertEqual(str(context.exception), "Parameter 'items' must have at least 1 items")
        with self.assertRaises(ToolError) as context:
            tool.check({"items": "not an array"})
        self.assertEqual(str(context.exception), "Parameter 'items' must be an array")
        with self.assertRaises(ToolError) as context:
            tool.check({"items": ["a", 1]})
        self.assertEqual(str(context.exception), "Parameter 'items[1]' must be a string")

    def test_object_array_parameter(self):
        tool = DummyTool([Parameter("items", "array param", ParameterType.Array([Parameter("text", "string param", ParameterType.String)]))])
        tool.check({"items": [{"text": "a"}, {"text": "b"}]})
        with self.assertRaises(ToolError) as context:
            tool.check({"items": [{"text": "a"}, 1]})
        self.assertEqual(str(context.exception), "Parameter 'items[1]' must be an object")
        with self.assertRaises(ToolError) as context:
            tool.check({"items": [{"text": 1}]})
        self.assertEqual(str(context.exception), "Parameter 'items[0].text' must be a string")
        with self.assertRaises(ToolError) as context:
            tool.check({"items": [{"text": "a"}, {}]})
        self.assertEqual(str(context.exception), "Missing required parameter: items[1].text")
        with self.assertRaises(ToolError) as context:
            tool.check({"items": [{"text": "a", "extra": "extra"}]})
        self.assertEqual(str(context.exception), "Unexpected arguments: items[0].extra")

    def test_mismatched_parameters(self):
        tool = DummyTool([Parameter("required", "required param", ParameterType.String)])
        with self.assertRaises(ToolError) as context:
            tool.check({})
        self.assertEqual(str(context.exception), "Missing required parameter: required")
        with self.assertRaises(ToolError) as context:
            tool.check({"required": "value", "extra": "extra"})
        self.assertEqual(str(context.exception), "Unexpected arguments: extra")
