import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ask.commands.memorize import MemorizeCommand

class TestMemorizeCommand(unittest.TestCase):
    @patch('ask.commands.memorize.get_agents_md_path')
    @patch('ask.commands.memorize.Path.cwd')
    def test_create_new_file(self, mock_cwd, mock_get_path):
        with tempfile.TemporaryDirectory() as temp_dir:
            agents_path = Path(temp_dir) / "AGENTS.md"
            mock_get_path.return_value = None
            mock_cwd.return_value = Path(temp_dir)

            MemorizeCommand.run("test memory", {})
            self.assertTrue(agents_path.exists())
            self.assertEqual(agents_path.read_text(), "- test memory\n")

    @patch('ask.commands.memorize.get_agents_md_path')
    def test_update_existing_file(self, mock_get_path):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md') as f:
            agents_path = Path(f.name)
            mock_get_path.return_value = agents_path
            f.write("existing content")
            f.flush()

            MemorizeCommand.run("new memory", {})
            self.assertEqual(agents_path.read_text(), "existing content\n- new memory\n")
