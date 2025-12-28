import tempfile
import unittest
from pathlib import Path

from ask.messages import Text
from ask.tools.list import ListTool

class TestListTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = ListTool()

    async def test_basic_listing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.txt").touch()
            (temp_path / "file2.py").touch()
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "nested.txt").touch()

            result = await self.tool.run(path=temp_path, ignore=[])
            assert isinstance(result, Text)
            lines = result.text.split('\n')
            self.assertEqual(lines[0], f"- {temp_path}/")
            self.assertEqual(lines[1], "  - file1.txt")
            self.assertEqual(lines[2], "  - file2.py")
            self.assertEqual(lines[3], "  - subdir/")
            self.assertEqual(lines[4], "    - nested.txt")

    async def test_ignore_patterns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "keep.txt").touch()
            (temp_path / "ignore.txt").touch()
            (temp_path / "test.py").touch()

            result = await self.tool.run(path=temp_path, ignore=["*.txt"])
            assert isinstance(result, Text)
            self.assertIn("- test.py", result.text)
            self.assertNotIn("- keep.txt", result.text)
            self.assertNotIn("- ignore.txt", result.text)

    async def test_ignored_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()
            (temp_path / "node_modules").mkdir()
            (temp_path / "node_modules" / "package.txt").touch()
            (temp_path / ".git").mkdir()
            (temp_path / ".git" / "config").touch()
            (temp_path / '.hidden').touch()

            result = await self.tool.run(path=temp_path, ignore=[])
            assert isinstance(result, Text)
            self.assertIn("- file.txt", result.text)
            self.assertIn("- node_modules/", result.text)
            self.assertNotIn("- package.txt", result.text)
            self.assertNotIn("- .git/", result.text)
            self.assertNotIn("- .hidden", result.text)
