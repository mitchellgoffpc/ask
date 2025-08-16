import tempfile
import unittest
from pathlib import Path
from ask.tools.list import ListTool


class TestListTool(unittest.TestCase):
    def setUp(self):
        self.tool = ListTool()

    def test_basic_listing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.txt").touch()
            (temp_path / "file2.py").touch()
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "nested.txt").touch()

            lines = self.tool.run({"path": str(temp_path)}).split('\n')
            self.assertEqual(lines[0], f"- {temp_path}/")
            self.assertEqual(lines[1], "  - file1.txt")
            self.assertEqual(lines[2], "  - file2.py")
            self.assertEqual(lines[3], "  - subdir/")
            self.assertEqual(lines[4], "    - nested.txt")

    def test_ignore_patterns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "keep.txt").touch()
            (temp_path / "ignore.txt").touch()
            (temp_path / "test.py").touch()

            result = self.tool.run({"path": str(temp_path), "ignore": ["*.txt"]})
            self.assertIn("- test.py", result)
            self.assertNotIn("- keep.txt", result)
            self.assertNotIn("- ignore.txt", result)

    def test_ignored_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()
            (temp_path / "node_modules").mkdir()
            (temp_path / "node_modules" / "package.txt").touch()
            (temp_path / ".git").mkdir()
            (temp_path / ".git" / "config").touch()
            (temp_path / '.hidden').touch()

            result = self.tool.run({"path": str(temp_path)})
            self.assertIn("- file.txt", result)
            self.assertIn("- node_modules/", result)
            self.assertNotIn("- package.txt", result)
            self.assertNotIn("- .git/", result)
            self.assertNotIn("- .hidden", result)
