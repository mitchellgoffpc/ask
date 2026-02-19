import asyncio
import unittest

import pytest

from ask.shells import PYTHON_SHELL


class TestPythonTool(unittest.IsolatedAsyncioTestCase):
    async def run_command(self, code: str, timeout_seconds: float = 10.) -> tuple[str, str]:
        nodes = PYTHON_SHELL.parse(code)
        return await PYTHON_SHELL.execute(nodes=nodes, timeout_seconds=timeout_seconds)

    async def test_basic_execution(self) -> None:
        result, _ = await self.run_command("print('hello world')")
        assert "hello world" in result

    async def test_expression_output(self) -> None:
        result, _ = await self.run_command("2 + 2")
        assert "4" in result

    async def test_variable_persistence(self) -> None:
        await self.run_command("x = 42")
        result, _ = await self.run_command("print(x)")
        assert "42" in result

    async def test_multiline_code(self) -> None:
        code = "for i in range(3):\n  print(f'Count: {i}')"
        result, _ = await self.run_command(code)
        assert "Count: 0" in result
        assert "Count: 1" in result
        assert "Count: 2" in result

    async def test_error_handling(self) -> None:
        _, exception = await self.run_command("1 / 0")
        assert 'ZeroDivisionError' in exception

    async def test_syntax_error(self) -> None:
        with pytest.raises(SyntaxError):
            PYTHON_SHELL.parse("def invalid_syntax(")

    async def test_task_timeout(self) -> None:
        start_time = asyncio.get_event_loop().time()
        with pytest.raises(TimeoutError) as context:
            await asyncio.create_task(self.run_command("import time; time.sleep(10)", timeout_seconds=0.1))
        assert "Code execution timed out" in str(context.value)
        assert asyncio.get_event_loop().time() - start_time < 1.0

        result, _ = await self.run_command("2 + 2")
        assert "4" in result
        assert asyncio.get_event_loop().time() - start_time < 1.0

    async def test_task_cancellation(self) -> None:
        task = asyncio.create_task(self.run_command("import time; time.sleep(10)"))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        start_time = asyncio.get_event_loop().time()
        result, _ = await self.run_command("2 + 2")
        assert "4" in result
        assert asyncio.get_event_loop().time() - start_time < 1.0
