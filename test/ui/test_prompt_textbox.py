import unittest
from unittest.mock import Mock
from ask.ui.styles import ansi_len
from ask.ui.__main__ import PromptTextBox

class TestPromptTextBox(unittest.TestCase):
    def test_prompt_textbox_creation_and_initialization(self):
        """Test PromptTextBox creation with bash mode handling."""
        handle_set_bash_mode = Mock()

        # Non-bash mode
        prompt_textbox = PromptTextBox(bash_mode=False, handle_set_bash_mode=handle_set_bash_mode)
        self.assertFalse(prompt_textbox.props['bash_mode'])
        self.assertEqual(prompt_textbox.props['handle_set_bash_mode'], handle_set_bash_mode)

        # Bash mode
        prompt_textbox = PromptTextBox(bash_mode=True, handle_set_bash_mode=handle_set_bash_mode)
        self.assertTrue(prompt_textbox.props['bash_mode'])

    def test_prompt_textbox_bash_mode_toggle(self):
        """Test bash mode toggling with exclamation mark and backspace."""
        handle_set_bash_mode = Mock()
        prompt_textbox = PromptTextBox(bash_mode=False, handle_set_bash_mode=handle_set_bash_mode, width=20)

        # Exclamation mark toggles to bash mode
        prompt_textbox.handle_input('!')
        handle_set_bash_mode.assert_called_once_with(True)

        handle_set_bash_mode.reset_mock()

        # Backspace in bash mode with empty content toggles back
        prompt_textbox.props['bash_mode'] = True
        prompt_textbox.state['content'] = ''
        prompt_textbox.handle_input('\x7f')
        handle_set_bash_mode.assert_called_once_with(False)

    def test_prompt_textbox_regular_input_in_bash_mode(self):
        """Test regular input handling in bash mode."""
        handle_set_bash_mode = Mock()
        prompt_textbox = PromptTextBox(bash_mode=True, handle_set_bash_mode=handle_set_bash_mode, width=20)

        # Regular character input works normally in bash mode
        prompt_textbox.handle_input('l')
        prompt_textbox.handle_input('s')
        self.assertEqual(prompt_textbox.state['content'], 'ls')
        handle_set_bash_mode.assert_not_called()

    def test_prompt_textbox_no_bash_toggle_with_content(self):
        """Test that bash mode doesn't toggle when there's content."""
        handle_set_bash_mode = Mock()
        prompt_textbox = PromptTextBox(bash_mode=False, handle_set_bash_mode=handle_set_bash_mode, width=20)
        prompt_textbox.state['content'] = 'some text'
        prompt_textbox.state['cursor_pos'] = len(prompt_textbox.state['content'])

        # Exclamation mark should be treated as regular input when there's content
        prompt_textbox.handle_input('!')
        self.assertEqual(prompt_textbox.state['content'], 'some text!')
        handle_set_bash_mode.assert_not_called()

    def test_prompt_textbox_no_bash_toggle_on_backspace_with_content(self):
        """Test that bash mode doesn't toggle on backspace when there's content."""
        handle_set_bash_mode = Mock()
        prompt_textbox = PromptTextBox(bash_mode=True, handle_set_bash_mode=handle_set_bash_mode, width=20)
        prompt_textbox.state['content'] = 'ls'
        prompt_textbox.state['cursor_pos'] = len(prompt_textbox.state['content'])

        # Backspace should work normally when there's content
        prompt_textbox.handle_input('\x7f')
        self.assertEqual(prompt_textbox.state['content'], 'l')
        handle_set_bash_mode.assert_not_called()

    def test_prompt_textbox_rendering_normal_mode(self):
        """Test prompt textbox rendering in normal mode."""
        handle_set_bash_mode = Mock()
        prompt_textbox = PromptTextBox(bash_mode=False, handle_set_bash_mode=handle_set_bash_mode, width=20)
        prompt_textbox.state['content'] = 'hello'
        prompt_textbox.state['cursor_pos'] = len(prompt_textbox.state['content'])

        rendered = prompt_textbox.render([])
        lines = rendered.split('\n')
        self.assertIn('>', rendered)  # Normal mode prompt
        self.assertIn('hello', rendered)
        self.assertTrue(len(lines) == 3)
        self.assertTrue(all(ansi_len(line) == 20 for line in lines))

    def test_prompt_textbox_rendering_bash_mode(self):
        """Test prompt textbox rendering in bash mode."""
        handle_set_bash_mode = Mock()
        prompt_textbox = PromptTextBox(bash_mode=True, handle_set_bash_mode=handle_set_bash_mode, width=20)
        prompt_textbox.state['content'] = 'ls -la'
        prompt_textbox.state['cursor_pos'] = len(prompt_textbox.state['content'])

        rendered = prompt_textbox.render([])
        lines = rendered.split('\n')
        self.assertIn('!', rendered)
        self.assertIn('ls -la', rendered)
        self.assertTrue(len(lines) == 3)
        self.assertTrue(all(ansi_len(line) == 20 for line in lines))
