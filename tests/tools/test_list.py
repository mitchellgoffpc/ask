import tempfile
import unittest
from pathlib import Path

from ask.messages import Text
from ask.tools.list import ListTool


class TestListTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = ListTool()

    async def run_tool(self, path: str, ignore: list[str]) -> str:
        args = {"path": path, "ignore": ignore}
        self.tool.check(args)
        artifacts = self.tool.process(args, self.tool.artifacts(args))
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_basic_listing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.txt").touch()
            (temp_path / "file2.py").touch()
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "nested.txt").touch()

            result = await self.run_tool(path=temp_dir, ignore=[])
            lines = result.split('\n')
            assert lines[0] == f"- {temp_path}/"
            assert lines[1] == "  - file1.txt"
            assert lines[2] == "  - file2.py"
            assert lines[3] == "  - subdir/"
            assert lines[4] == "    - nested.txt"

    async def test_ignore_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "keep.txt").touch()
            (temp_path / "ignore.txt").touch()
            (temp_path / "test.py").touch()

            result = await self.run_tool(path=temp_dir, ignore=["*.txt"])
            assert "- test.py" in result
            assert "- keep.txt" not in result
            assert "- ignore.txt" not in result

    async def test_ignored_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()
            (temp_path / "node_modules").mkdir()
            (temp_path / "node_modules" / "package.txt").touch()
            (temp_path / ".git").mkdir()
            (temp_path / ".git" / "config").touch()
            (temp_path / '.hidden').touch()

            result = await self.run_tool(path=temp_dir, ignore=[])
            assert "- file.txt" in result
            assert "- node_modules/" in result
            assert "- package.txt" not in result
            assert "- .git/" not in result
            assert "- .hidden" not in result
