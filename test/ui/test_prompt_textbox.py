import unittest
from unittest.mock import Mock
from ask.ui.styles import ansi_len, ansi_strip
from ask.ui.__main__ import PromptTextBox


class TestPromptTextBoxInputHandling(unittest.TestCase):
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
        prompt_textbox.state['content'] = 'ls -la'
        prompt_textbox.state['cursor_pos'] = len(prompt_textbox.state['content'])

        # Backspace should work normally when there's content
        prompt_textbox.handle_input('\x7f')
        self.assertEqual(prompt_textbox.state['content'], 'ls -l')
        handle_set_bash_mode.assert_not_called()


class TestPromptTextBoxRendering(unittest.TestCase):
    def test_prompt_textbox_rendering(self):
        """Test prompt textbox rendering in both normal and bash modes."""
        handle_set_bash_mode = Mock()

        test_cases = [
            (False, 'hello', '>'),
            (True, 'ls -la', '!')
        ]

        for bash_mode, content, expected_marker in test_cases:
            with self.subTest(bash_mode=bash_mode):
                prompt_textbox = PromptTextBox(bash_mode=bash_mode, handle_set_bash_mode=handle_set_bash_mode, width=20)
                prompt_textbox.state['content'] = content
                prompt_textbox.state['cursor_pos'] = len(content)

                rendered = prompt_textbox.render([])
                lines = rendered.split('\n')
                self.assertIn(expected_marker, rendered)
                self.assertIn(content, rendered)
                self.assertTrue(len(lines) == 3)
                self.assertTrue(all(ansi_len(line) == 20 for line in lines))

    def test_prompt_textbox_rendering_with_wrapping_lines(self):
        """Test prompt textbox renders wrapped lines correctly with proper padding."""
        textbox = PromptTextBox(bash_mode=False, handle_set_bash_mode=Mock(), width=15)
        textbox.state['content'] = 'This is a long line that should wrap correctly.'
        textbox.state['cursor_pos'] = len(textbox.state['content'])
        rendered = textbox.render([])
        lines = rendered.split('\n')

        # All lines should have correct width
        self.assertGreater(len(lines), 3)
        for line in lines:
            self.assertEqual(ansi_len(line), 15)

        # Check that content lines have correct padding
        for i, line in enumerate(lines[1:-1]):
            prefix = ' > ' if i == 0 else '   '
            self.assertEqual(ansi_strip(line)[1:4], prefix)
