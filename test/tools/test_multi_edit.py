import tempfile
import unittest
from pathlib import Path
from ask.tools.multi_edit import MultiEditTool
from ask.tools.base import ToolError


class TestMultiEditTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = MultiEditTool()

    async def run_tool(self, file_path: str, edits: list[dict]) -> str:
        args = self.tool.check({'file_path': file_path, 'edits': edits})
        return await self.tool.run(**args)

    async def test_multiple_edits(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("Hello world\nThis is a test\nGoodbye world")
            f.flush()

            edits = [
                {'old_string': 'Hello', 'new_string': 'Hi'},
                {'old_string': 'test', 'new_string': 'example'},
                {'old_string': 'Goodbye', 'new_string': 'Farewell'}
            ]
            result = await self.run_tool(file_path=f.name, edits=edits)
            content = Path(f.name).read_text()
            self.assertEqual(content, "Hi world\nThis is a example\nFarewell world")
            self.assertIn("The file", result)
            self.assertIn("has been updated with 3 edits.", result)

    async def test_replace_all_in_multiple_edits(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("test foo test\nbar test foo")
            f.flush()

            edits = [
                {'old_string': 'test', 'new_string': 'example', 'replace_all': True},
                {'old_string': 'foo', 'new_string': 'baz', 'replace_all': True}
            ]
            await self.run_tool(file_path=f.name, edits=edits)
            content = Path(f.name).read_text()
            self.assertEqual(content, "example baz example\nbar example baz")

    async def test_sequential_edits(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("original text")
            f.flush()

            edits = [
                {'old_string': 'original', 'new_string': 'modified'},
                {'old_string': 'modified text', 'new_string': 'final result'}
            ]
            await self.run_tool(file_path=f.name, edits=edits)
            content = Path(f.name).read_text()
            self.assertEqual(content, "final result")

    async def test_multiple_occurrences_without_replace_all(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("foo bar foo")
            f.flush()

            edits = [{'old_string': 'foo', 'new_string': 'baz'}]
            with self.assertRaises(ToolError) as cm:
                await self.run_tool(file_path=f.name, edits=edits)
            self.assertIn("Found 2 matches", str(cm.exception))
