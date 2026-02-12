import unittest

import pytest

from ask.messages import Text
from ask.tools.base import ToolError
from ask.tools.python import PythonTool


class TestPythonTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = PythonTool()

    async def run_tool(self, code: str, timeout_seconds: int = 10) -> str:
        args = {"code": code, "timeout": timeout_seconds * 1000}
        self.tool.check(args)
        artifacts = self.tool.process(args, self.tool.artifacts(args))
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_basic_execution(self) -> None:
        result = await self.run_tool("print('hello world')")
        assert "hello world" in result

    async def test_expression_output(self) -> None:
        result = await self.run_tool("2 + 2")
        assert "4" in result

    async def test_error_handling(self) -> None:
        with pytest.raises(ToolError) as context:
            await self.run_tool("1 / 0")
        assert isinstance(context.value, ToolError)
        assert 'ZeroDivisionError' in str(context.value)

    async def test_syntax_error(self) -> None:
        with pytest.raises(ToolError) as context:
            await self.run_tool("def invalid_syntax(")
        assert isinstance(context.value, ToolError)
        assert isinstance(context.value.__cause__, SyntaxError)
