import tempfile
import unittest
from pathlib import Path
from ask.tools.write import WriteTool


class TestWriteTool(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tool = WriteTool()

    async def test_create_new_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_file.txt"
            content = "Hello, world!"
            result = await self.tool.run({"file_path": str(file_path), "content": content})

            self.assertEqual(file_path.read_text(encoding='utf-8'), content)
            self.assertIn("File created successfully", result)

    async def test_overwrite_existing_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as f:
            f.write("original content")
            f.flush()
            new_content = "new content"
            result = await self.tool.run({"file_path": f.name, "content": new_content})

            self.assertEqual(Path(f.name).read_text(encoding='utf-8'), new_content)
            self.assertIn("File updated successfully", result)

    async def test_create_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nested" / "dirs" / "file.txt"
            content = "test content"
            result = await self.tool.run({"file_path": str(file_path), "content": content})

            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.read_text(encoding='utf-8'), content)
            self.assertIn("File created successfully", result)
