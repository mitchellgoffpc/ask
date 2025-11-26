import unittest
import asyncio

from ask.shells import PYTHON_SHELL

class TestPythonTool(unittest.IsolatedAsyncioTestCase):
    async def run_command(self, code, timeout_seconds = 10):
        nodes = PYTHON_SHELL.parse(code)
        output, exception = await PYTHON_SHELL.execute(nodes=nodes, timeout_seconds=timeout_seconds)
        if exception:
            raise exception
        return output

    async def test_basic_execution(self):
        result = await self.run_command("print('hello world')")
        self.assertIn("hello world", result)

    async def test_expression_output(self):
        result = await self.run_command("2 + 2")
        self.assertIn("4", result)

    async def test_variable_persistence(self):
        await self.run_command("x = 42")
        result = await self.run_command("print(x)")
        self.assertIn("42", result)

    async def test_multiline_code(self):
        code = "for i in range(3):\n  print(f'Count: {i}')"
        result = await self.run_command(code)
        self.assertIn("Count: 0", result)
        self.assertIn("Count: 1", result)
        self.assertIn("Count: 2", result)

    async def test_error_handling(self):
        with self.assertRaises(ZeroDivisionError):
            await self.run_command("1 / 0")

    async def test_syntax_error(self):
        with self.assertRaises(SyntaxError):
            PYTHON_SHELL.parse("def invalid_syntax(")

    async def test_task_timeout(self):
        start_time = asyncio.get_event_loop().time()
        with self.assertRaises(TimeoutError) as context:
            await asyncio.create_task(self.run_command("import time; time.sleep(10)", timeout_seconds=0.1))
        self.assertIn("Code execution timed out", str(context.exception))
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

        result = await self.run_command("2 + 2")
        self.assertIn("4", result)
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

    async def test_task_cancellation(self):
        task = asyncio.create_task(self.run_command("import time; time.sleep(10)"))
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        start_time = asyncio.get_event_loop().time()
        result = await self.run_command("2 + 2")
        self.assertIn("4", result)
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)
