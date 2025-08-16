import tempfile
import unittest
from pathlib import Path
from ask.tools.glob_ import GlobTool


class TestGlobTool(unittest.TestCase):
    def setUp(self):
        self.tool = GlobTool()

    def test_basic_glob(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.txt").touch()
            (temp_path / "file2.py").touch()
            (temp_path / "test.txt").touch()

            lines = self.tool.run({"path": str(temp_path), "pattern": "*.txt"}).split('\n')
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], "Found 2 files")
            self.assertEqual(lines[1], f"- {temp_path / 'file1.txt'}")
            self.assertEqual(lines[2], f"- {temp_path / 'test.txt'}")

    def test_recursive_glob(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "root.py").touch()
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "sub.py").touch()
            (temp_path / "subdir" / "other.txt").touch()

            result = self.tool.run({"path": str(temp_path), "pattern": "**/*.py"})
            self.assertTrue(result.startswith("Found 2 files"))
            self.assertIn("root.py", result)
            self.assertIn("sub.py", result)
            self.assertNotIn("other.txt", result)

    def test_no_matches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()

            result = self.tool.run({"path": str(temp_path), "pattern": "*.nonexistent"})
            self.assertEqual(result, "Found 0 files")

    def test_directory_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()
            (temp_path / "somedir").mkdir()

            result = self.tool.run({"path": str(temp_path), "pattern": "*"})
            self.assertTrue(result.startswith("Found 1 files"))
            self.assertIn("file.txt", result)
            self.assertNotIn("somedir", result)
