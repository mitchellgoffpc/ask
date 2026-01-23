import asyncio
import unittest

from ask.messages import Text
from ask.tools.base import ToolError
from ask.tools.bash import BashTool

class TestBashTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = BashTool()

    async def run_tool(self, command: str, timeout: int = 10000) -> str:
        args = {"command": command, "timeout": timeout}
        self.tool.check(args)
        result = await self.tool.run(args, self.tool.artifacts(args))
        assert isinstance(result, Text)
        return result.text

    async def test_command_stdout(self):
        result = await self.run_tool(command="echo hello", timeout=10000)
        self.assertEqual(result, "hello")

    async def test_command_stderr(self):
        result = await self.run_tool(command="echo error 1>&2", timeout=10000)
        self.assertEqual(result, "error")

    async def test_command_error(self):
        with self.assertRaises(ToolError) as context:
            await self.run_tool(command="ls /nonexistant", timeout=10000)
        self.assertIn("No such file or directory", str(context.exception))

    async def test_task_timeout(self):
        start_time = asyncio.get_event_loop().time()
        with self.assertRaises(ToolError) as context:
            await asyncio.create_task(self.run_tool(command="sleep 10", timeout=100))
        self.assertIn("Command timed out", str(context.exception))
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

        result = await self.run_tool(command="echo hello", timeout=10000)
        self.assertEqual(result, "hello")
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

    async def test_task_cancellation(self):
        start_time = asyncio.get_event_loop().time()
        task = asyncio.create_task(self.run_tool(command="sleep 10", timeout=10000))
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        result = await self.run_tool(command="echo hello", timeout=10000)
        self.assertEqual(result, "hello")
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)
