import tempfile
import unittest
from pathlib import Path
from typing import Any

from ask.messages import Text
from ask.tools.grep import GrepTool

class TestGrepTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = GrepTool()

    async def run_tool(self, **kwargs: Any) -> str:
        self.tool.check(kwargs)
        artifacts = self.tool.process(kwargs, self.tool.artifacts(kwargs))
        result = await self.tool.run(kwargs, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_files_with_matches_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "match.txt").write_text("hello world")
            (temp_path / "nomatch.txt").write_text("goodbye")

            result = await self.run_tool(pattern='hello', pathspec=str(temp_path))
            lines = result.split('\n')
            self.assertEqual(lines[0], "Found 1 files")
            self.assertEqual(lines[1], f"{temp_path}/match.txt")

    async def test_count_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.txt").write_text("test test test")

            result = await self.run_tool(pattern='test', pathspec=str(temp_path), output_mode='count')
            lines = result.split('\n')
            self.assertEqual(lines[0], "Found 1 files")
            self.assertEqual(lines[1], f"{temp_path}/test.txt:3")

    async def test_content_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.txt").write_text("line1\nhello world\nline3")

            result = await self.run_tool(pattern='hello', pathspec=str(temp_path), output_mode='content', **{'-n': True})
            lines = result.split('\n')
            self.assertEqual(lines[0], "Found 1 matches")
            self.assertEqual(lines[1], f"{temp_path}/test.txt:2:hello world")

    async def test_context_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.txt").write_text("before\nmatch\nmiddle\nmatch\nafter\n\n\nmatch")

            result = await self.run_tool(pattern='match', pathspec=str(temp_path), output_mode='content', **{'-C': 1})
            lines = result.split('\n')
            self.assertEqual(len(lines), 9)
            self.assertEqual(lines[0], "Found 3 matches")
            self.assertEqual(lines[1], f"{temp_path}/test.txt:before")
            self.assertEqual(lines[2], f"{temp_path}/test.txt:match")
            self.assertEqual(lines[3], f"{temp_path}/test.txt:middle")
            self.assertEqual(lines[4], f"{temp_path}/test.txt:match")
            self.assertEqual(lines[5], f"{temp_path}/test.txt:after")
            self.assertEqual(lines[6], "--")
            self.assertEqual(lines[7], f"{temp_path}/test.txt:")
            self.assertEqual(lines[8], f"{temp_path}/test.txt:match")

    async def test_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.txt").write_text("HELLO world")

            result = await self.run_tool(pattern='hello', pathspec=str(temp_path), **{'-i': True})
            lines = result.split('\n')
            self.assertEqual(lines[0], "Found 1 files")
            self.assertEqual(lines[1], f"{temp_path}/test.txt")

    async def test_glob_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "match.py").write_text("python code")
            (temp_path / "match.txt").write_text("python code")

            result = await self.run_tool(pattern='python', pathspec=str(temp_path / '*.py'))
            lines = result.split('\n')
            self.assertEqual(lines[0], "Found 1 files")
            self.assertEqual(lines[1], f"{temp_path}/match.py")

    async def test_head_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            for i in range(5):
                (temp_path / f"file{i}.txt").write_text("match")

            result = await self.run_tool(pattern='match', pathspec=str(temp_path), head_limit=2)
            lines = result.split('\n')
            self.assertEqual(lines[0], "Found 5 files")
            self.assertEqual(len(lines) - 1, 2)

    async def test_no_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.txt").write_text("hello world")

            result = await self.run_tool(pattern='nonexistent', pathspec=str(temp_path))
            self.assertEqual(result, "No matches found")
