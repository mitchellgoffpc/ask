import tempfile
import unittest
from pathlib import Path

from ask.messages import Text
from ask.tools.glob_ import GlobTool


class TestGlobTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = GlobTool()

    async def run_tool(self, path: str, pattern: str) -> str:
        args = {"path": path, "pattern": pattern}
        self.tool.check(args)
        artifacts = self.tool.process(args, self.tool.artifacts(args))
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_basic_glob(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file1.txt").touch()
            (temp_path / "file2.py").touch()
            (temp_path / "test.txt").touch()

            result = await self.run_tool(path=temp_dir, pattern="*.txt")
            lines = result.split('\n')
            results = sorted(lines[1:])
            assert len(lines) == 3
            assert lines[0] == "Found 2 files"
            assert results[0] == f"- {temp_path / 'file1.txt'}"
            assert results[1] == f"- {temp_path / 'test.txt'}"

    async def test_recursive_glob(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "root.py").touch()
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "sub.py").touch()
            (temp_path / "subdir" / "other.txt").touch()

            result = await self.run_tool(path=temp_dir, pattern="**/*.py")
            assert result.startswith("Found 2 files")
            assert "root.py" in result
            assert "sub.py" in result
            assert "other.txt" not in result

    async def test_no_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()

            result = await self.run_tool(path=temp_dir, pattern="*.nonexistent")
            assert result == "Found 0 files"

    async def test_directory_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "file.txt").touch()
            (temp_path / "somedir").mkdir()

            result = await self.run_tool(path=temp_dir, pattern="*")
            assert result.startswith("Found 1 files")
            assert "file.txt" in result
            assert "somedir" not in result
