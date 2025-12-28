import tempfile
import unittest
from pathlib import Path

from ask.messages import Text
from ask.tools.read import ReadTool

class TestReadTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = ReadTool()

    async def test_basic_read(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("line 1\nline 2\nline 3\n")
            f.flush()

            result = await self.tool.run(file_path=Path(f.name), offset=0, limit=1000)
            assert isinstance(result, Text)
            lines = result.text.split('\n')
            self.assertEqual(len(lines), 4)
            self.assertEqual(lines[0], "     1→line 1")
            self.assertEqual(lines[1], "     2→line 2")
            self.assertEqual(lines[2], "     3→line 3")
            self.assertEqual(lines[3], "     4→")

    async def test_offset_and_limit(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5")
            f.flush()

            result = await self.tool.run(file_path=Path(f.name), offset=2, limit=2)
            assert isinstance(result, Text)
            lines = result.text.split('\n')
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], "     3→line 3")
            self.assertEqual(lines[1], "     4→line 4")
            self.assertEqual(lines[2], "... [truncated, file contains more than 4 lines]")

    async def test_line_truncation(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write(f"{'x' * 2500}\nshort line\n")
            f.flush()

            result = await self.tool.run(file_path=Path(f.name), offset=0, limit=1000)
            assert isinstance(result, Text)
            lines = result.text.split('\n')
            self.assertTrue(lines[0].endswith("... [truncated]"))
            self.assertEqual(lines[1], "     2→short line")

    async def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            result = await self.tool.run(file_path=Path(f.name), offset=0, limit=1000)
            assert isinstance(result, Text)
            self.assertEqual(result.text, "     1→")
