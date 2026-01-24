import unittest

from ask.messages import Text
from ask.tools.python import PythonTool
from ask.tools.base import ToolError

class TestPythonTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = PythonTool()

    async def run_tool(self, code: str, timeout_seconds: int = 10) -> str:
        args = {"code": code, "timeout": timeout_seconds * 1000}
        self.tool.check(args)
        artifacts = self.tool.process(args, self.tool.artifacts(args))
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_basic_execution(self):
        result = await self.run_tool("print('hello world')")
        self.assertIn("hello world", result)

    async def test_expression_output(self):
        result = await self.run_tool("2 + 2")
        self.assertIn("4", result)

    async def test_error_handling(self):
        with self.assertRaises(ToolError) as context:
            await self.run_tool("1 / 0")
        self.assertIsInstance(context.exception, ToolError)
        self.assertIn('ZeroDivisionError', str(context.exception))

    async def test_syntax_error(self):
        with self.assertRaises(ToolError) as context:
            await self.run_tool("def invalid_syntax(")
        self.assertIsInstance(context.exception, ToolError)
        self.assertIsInstance(context.exception.__cause__, SyntaxError)
