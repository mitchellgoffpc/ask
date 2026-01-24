import tempfile
import unittest
from pathlib import Path

from ask.messages import Text
from ask.tools.list import ListTool

class TestListTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = ListTool()

    async def run_tool(self, path: str, ignore: list[str]) -> str:
        args = {"path": path, "ignore": ignore}
        self.tool.check(args)
        artifacts = self.tool.process(args, self.tool.artifacts(args))
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_basic_listing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.txt").touch()
            (temp_path / "file2.py").touch()
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "nested.txt").touch()

            result = await self.run_tool(path=temp_dir, ignore=[])
            lines = result.split('\n')
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

            result = await self.run_tool(path=temp_dir, ignore=["*.txt"])
            self.assertIn("- test.py", result)
            self.assertNotIn("- keep.txt", result)
            self.assertNotIn("- ignore.txt", result)

    async def test_ignored_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()
            (temp_path / "node_modules").mkdir()
            (temp_path / "node_modules" / "package.txt").touch()
            (temp_path / ".git").mkdir()
            (temp_path / ".git" / "config").touch()
            (temp_path / '.hidden').touch()

            result = await self.run_tool(path=temp_dir, ignore=[])
            self.assertIn("- file.txt", result)
            self.assertIn("- node_modules/", result)
            self.assertNotIn("- package.txt", result)
            self.assertNotIn("- .git/", result)
            self.assertNotIn("- .hidden", result)
