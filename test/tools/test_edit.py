import tempfile
import unittest
from pathlib import Path

import pytest

from ask.messages import Text
from ask.tools.base import ToolError
from ask.tools.edit import EditTool


class TestEditTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = EditTool()

    async def run_tool(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        args = {'file_path': file_path, 'old_string': old_string, 'new_string': new_string, 'replace_all': replace_all}
        self.tool.check(args)
        artifacts = self.tool.process(args, self.tool.artifacts(args))
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_basic_replace(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("Hello world\nThis is a test")
            f.flush()

            lines = (await self.run_tool(file_path=f.name, old_string="world", new_string="universe", replace_all=False)).split('\n')
            content = Path(f.name).read_text()
            assert content == "Hello universe\nThis is a test"
            assert f"The file {f.name} has been updated." in lines[0]
            assert lines[1] == "     1→Hello universe"
            assert lines[2] == "     2→This is a test"

    async def test_replace_all(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("test test test\ntest again")
            f.flush()

            result = await self.run_tool(file_path=f.name, old_string="test", new_string="example", replace_all=True)
            content = Path(f.name).read_text()
            assert content == "example example example\nexample again"
            assert "all occurrences of 'test' have been replaced with 'example'" in result

    async def test_multiple_occurrences_without_replace_all(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("foo bar foo")
            f.flush()

            with pytest.raises(ToolError) as cm:
                await self.run_tool(file_path=f.name, old_string="foo", new_string="baz", replace_all=False)
            assert "Found 2 matches" in str(cm.value)

    async def test_response_snippet(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write('\n'.join(chr(65+i) for i in range(26)))  # A-Z on separate lines
            f.flush()

            lines = (await self.run_tool(file_path=f.name, old_string="L\nM\nN", new_string="foo\nbar\nbaz", replace_all=False)).split('\n')
            assert lines[1] == "     7→G"
            assert lines[6] == "    12→foo"
            assert lines[-1] == "    19→S"
