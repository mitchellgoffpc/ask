import tempfile
import unittest
from pathlib import Path

from ask.messages import Text
from ask.tools.write import WriteTool


class TestWriteTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = WriteTool()

    async def run_tool(self, file_path: str, content: str) -> str:
        args = {"file_path": file_path, "content": content}
        self.tool.check(args)
        artifacts = self.tool.process(args, self.tool.artifacts(args))
        result = await self.tool.run(args, artifacts)
        assert isinstance(result, Text)
        return result.text

    async def test_create_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_file.txt"
            content = "Hello, world!"
            result = await self.run_tool(file_path=str(file_path), content=content)

            assert file_path.read_text(encoding='utf-8') == content
            assert "File created successfully" in result

    async def test_overwrite_existing_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("original content")
            f.flush()
            new_content = "new content"
            result = await self.run_tool(file_path=f.name, content=new_content)

            assert Path(f.name).read_text(encoding='utf-8') == new_content
            assert "File updated successfully" in result

    async def test_create_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nested" / "dirs" / "file.txt"
            content = "test content"
            result = await self.run_tool(file_path=str(file_path), content=content)

            assert file_path.exists()
            assert file_path.read_text(encoding='utf-8') == content
            assert "File created successfully" in result
