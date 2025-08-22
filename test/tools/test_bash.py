import asyncio
import unittest
from ask.tools.base import ToolError
from ask.tools.bash import BashTool


class TestBashTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = BashTool()

    async def test_command_stdout(self):
        result = await self.tool.run(command="echo hello", timeout_seconds=10)
        self.assertEqual(result, "hello")

    async def test_command_stderr(self):
        result = await self.tool.run(command="echo error 1>&2", timeout_seconds=10)
        self.assertEqual(result, "error")

    async def test_command_error(self):
        with self.assertRaises(ToolError) as context:
            await self.tool.run(command="ls /nonexistant", timeout_seconds=10)
        self.assertEqual(str(context.exception), "ls: cannot access '/nonexistant': No such file or directory")

    async def test_task_timeout(self):
        start_time = asyncio.get_event_loop().time()
        with self.assertRaises(ToolError) as context:
            await asyncio.create_task(self.tool.run(command="sleep 10", timeout_seconds=0.1))
        self.assertIn("Command timed out", str(context.exception))
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

        result = await self.tool.run(command="echo hello", timeout_seconds=10)
        self.assertEqual(result, "hello")
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

    async def test_task_cancellation(self):
        task = asyncio.create_task(self.tool.run(command="sleep 10", timeout_seconds=10))
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        start_time = asyncio.get_event_loop().time()
        result = await self.tool.run(command="echo hello", timeout_seconds=10)
        self.assertEqual(result, "hello")
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)
