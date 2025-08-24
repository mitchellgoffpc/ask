import tempfile
import unittest
from pathlib import Path
from ask.tools.edit import EditTool
from ask.tools.base import ToolError


class TestEditTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = EditTool()

    async def run_tool(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        args = self.tool.check({'file_path': file_path, 'old_string': old_string, 'new_string': new_string, 'replace_all': replace_all})
        return await self.tool.run(**args)

    async def test_basic_replace(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("Hello world\nThis is a test")
            f.flush()

            lines = (await self.run_tool(file_path=f.name, old_string="world", new_string="universe", replace_all=False)).split('\n')
            content = Path(f.name).read_text()
            self.assertEqual(content, "Hello universe\nThis is a test")
            self.assertIn(f"The file {f.name} has been updated.", lines[0])
            self.assertEqual(lines[1], "     1→Hello universe")
            self.assertEqual(lines[2], "     2→This is a test")

    async def test_replace_all(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("test test test\ntest again")
            f.flush()

            result = await self.run_tool(file_path=f.name, old_string="test", new_string="example", replace_all=True)
            content = Path(f.name).read_text()
            self.assertEqual(content, "example example example\nexample again")
            self.assertIn("all occurrences of 'test' have been replaced with 'example'", result)

    async def test_multiple_occurrences_without_replace_all(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("foo bar foo")
            f.flush()

            with self.assertRaises(ToolError) as cm:
                await self.run_tool(file_path=f.name, old_string="foo", new_string="baz", replace_all=False)
            self.assertIn("Found 2 matches", str(cm.exception))

    async def test_response_snippet(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write('\n'.join(chr(65+i) for i in range(26)))  # A-Z on separate lines
            f.flush()

            lines = (await self.run_tool(file_path=f.name, old_string="L\nM\nN", new_string="foo\nbar\nbaz", replace_all=False)).split('\n')
            self.assertEqual(lines[1], "     7→G")
            self.assertEqual(lines[6], "    12→foo")
            self.assertEqual(lines[-1], "    19→S")
