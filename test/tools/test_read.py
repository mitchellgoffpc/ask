import tempfile
import unittest

from ask.messages import Text
from ask.tools.read import ReadTool

class TestReadTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = ReadTool()

    async def run_tool(self, file_path: str, offset: int = 0, limit: int = 1000) -> str:
        args = {"file_path": file_path, "offset": offset, "limit": limit}
        self.tool.check(args)
        artifacts = self.tool.process(args, self.tool.artifacts(args))
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_basic_read(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("line 1\nline 2\nline 3\n")
            f.flush()

            result = await self.run_tool(file_path=f.name, offset=0, limit=1000)
            lines = result.split('\n')
            self.assertEqual(len(lines), 4)
            self.assertEqual(lines[0], "     1→line 1")
            self.assertEqual(lines[1], "     2→line 2")
            self.assertEqual(lines[2], "     3→line 3")
            self.assertEqual(lines[3], "     4→")

    async def test_offset_and_limit(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5")
            f.flush()

            result = await self.run_tool(file_path=f.name, offset=2, limit=2)
            lines = result.split('\n')
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], "     3→line 3")
            self.assertEqual(lines[1], "     4→line 4")
            self.assertEqual(lines[2], "... [truncated, file contains more than 4 lines]")

    async def test_line_truncation(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write(f"{'x' * 2500}\nshort line\n")
            f.flush()

            result = await self.run_tool(file_path=f.name, offset=0, limit=1000)
            lines = result.split('\n')
            self.assertTrue(lines[0].endswith("... [truncated]"))
            self.assertEqual(lines[1], "     2→short line")

    async def test_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            result = await self.run_tool(file_path=f.name, offset=0, limit=1000)
            self.assertEqual(result, "     1→")
