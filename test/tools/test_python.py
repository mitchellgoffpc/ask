import unittest
import asyncio
from ask.tools.python import PythonTool
from ask.tools.base import ToolError


class TestPythonTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = PythonTool()

    async def test_basic_execution(self):
        result = await self.tool.run({"code": "print('hello world')"})
        self.assertIn("hello world", result)

    async def test_expression_output(self):
        result = await self.tool.run({"code": "2 + 2"})
        self.assertIn("4", result)

    async def test_variable_persistence(self):
        await self.tool.run({"code": "x = 42"})
        result = await self.tool.run({"code": "print(x)"})
        self.assertIn("42", result)

    async def test_multiline_code(self):
        code = "for i in range(3):\n  print(f'Count: {i}')"
        result = await self.tool.run({"code": code})
        self.assertIn("Count: 0", result)
        self.assertIn("Count: 1", result)
        self.assertIn("Count: 2", result)

    async def test_error_handling(self):
        result = await self.tool.run({"code": "1 / 0"})
        self.assertIn("ZeroDivisionError", result)

    async def test_syntax_error(self):
        with self.assertRaises(ToolError) as context:
            await self.tool.run({"code": "def invalid_syntax("})
        self.assertIsInstance(context.exception.__cause__, SyntaxError)

    async def test_task_timeout(self):
        start_time = asyncio.get_event_loop().time()
        with self.assertRaises(ToolError) as context:
            await asyncio.create_task(self.tool.run({"code": "import time; time.sleep(10)", "timeout": 100}))
        self.assertIn("Code execution timed out", str(context.exception))
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

        result = await self.tool.run({"code": "2 + 2"})
        self.assertIn("4", result)
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

    async def test_task_cancellation(self):
        task = asyncio.create_task(self.tool.run({"code": "import time; time.sleep(10)"}))
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        start_time = asyncio.get_event_loop().time()
        result = await self.tool.run({"code": "2 + 2"})
        self.assertIn("4", result)
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

    def tearDown(self):
        if self.tool.worker_process:
            self.tool._cleanup_worker()
