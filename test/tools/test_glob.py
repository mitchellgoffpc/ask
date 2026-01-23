import tempfile
import unittest
from pathlib import Path

from ask.messages import Text
from ask.tools.glob_ import GlobTool

class TestGlobTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = GlobTool()

    async def run_tool(self, path: str, pattern: str) -> str:
        args = {"path": path, "pattern": pattern}
        self.tool.check(args)
        artifacts = self.tool.artifacts(args)
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_basic_glob(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.txt").touch()
            (temp_path / "file2.py").touch()
            (temp_path / "test.txt").touch()

            result = await self.run_tool(path=temp_dir, pattern="*.txt")
            lines = result.split('\n')
            results = sorted(lines[1:])
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], "Found 2 files")
            self.assertEqual(results[0], f"- {temp_path / 'file1.txt'}")
            self.assertEqual(results[1], f"- {temp_path / 'test.txt'}")

    async def test_recursive_glob(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "root.py").touch()
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "sub.py").touch()
            (temp_path / "subdir" / "other.txt").touch()

            result = await self.run_tool(path=temp_dir, pattern="**/*.py")
            self.assertTrue(result.startswith("Found 2 files"))
            self.assertIn("root.py", result)
            self.assertIn("sub.py", result)
            self.assertNotIn("other.txt", result)

    async def test_no_matches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()

            result = await self.run_tool(path=temp_dir, pattern="*.nonexistent")
            self.assertEqual(result, "Found 0 files")

    async def test_directory_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()
            (temp_path / "somedir").mkdir()

            result = await self.run_tool(path=temp_dir, pattern="*")
            self.assertTrue(result.startswith("Found 1 files"))
            self.assertIn("file.txt", result)
            self.assertNotIn("somedir", result)
