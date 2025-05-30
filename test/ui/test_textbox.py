import unittest
from unittest.mock import Mock
from ask.ui.components import Spacing
from ask.ui.styles import ansi_len, ansi_strip
from ask.ui.textbox import TextBox


class TestTextBoxCreation(unittest.TestCase):
    def test_textbox_creation(self):
        """Test TextBox component creation with various props."""
        # Basic creation
        textbox = TextBox(width=50)
        self.assertEqual(textbox.props['width'], 50)
        self.assertIsNone(textbox.props['handle_change'])
        self.assertIsNone(textbox.props['handle_submit'])
        self.assertEqual(textbox.props['placeholder'], "")
        self.assertTrue(textbox.leaf)
        self.assertEqual(textbox.state['content'], '')
        self.assertEqual(textbox.state['cursor_pos'], 0)

        # With callbacks
        handle_change = Mock()
        handle_submit = Mock()
        textbox = TextBox(width=30, handle_change=handle_change, handle_submit=handle_submit, placeholder="Enter text...")
        self.assertEqual(textbox.props['width'], 30)
        self.assertEqual(textbox.props['handle_change'], handle_change)
        self.assertEqual(textbox.props['handle_submit'], handle_submit)
        self.assertEqual(textbox.props['placeholder'], "Enter text...")

    def test_textbox_line_wrapping_methods(self):
        """Test line wrapping and cursor position calculation methods."""
        textbox = TextBox(width=5)  # Small width for testing
        textbox.state['content'] = 'Hello World'
        textbox.state['cursor_pos'] = 8

        # Test cursor line/col calculation
        line, col = textbox.get_cursor_line_col()
        self.assertEqual(line, 2)
        self.assertEqual(col, 2)

        # Test total lines calculation
        total_lines = textbox.get_total_lines()
        self.assertGreater(total_lines, 0)

        # Test line start/end position calculation
        line_start = textbox.get_line_start_position(0)
        line_end = textbox.get_line_end_position(0)
        self.assertGreaterEqual(line_end, line_start)


class TestTextBoxInputHandling(unittest.TestCase):
    def test_textbox_basic_character_input(self):
        """Test character input and insertion at various cursor positions."""
        textbox = TextBox(width=20)

        # Insert at end
        textbox.handle_input('A')
        textbox.handle_input('B')
        self.assertEqual(textbox.state['content'], 'AB')
        self.assertEqual(textbox.state['cursor_pos'], 2)

        # Insert in the middle
        textbox.state['cursor_pos'] = 1
        textbox.handle_input('X')
        self.assertEqual(textbox.state['content'], 'AXB')
        self.assertEqual(textbox.state['cursor_pos'], 2)

    def test_textbox_backspace_handling(self):
        """Test backspace handling."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello'
        textbox.state['cursor_pos'] = 5

        # Backspace removes character before cursor
        textbox.handle_input('\x7f')
        self.assertEqual(textbox.state['content'], 'Hell')
        self.assertEqual(textbox.state['cursor_pos'], 4)

        # Backspace in the middle removes character before cursor
        textbox.state['cursor_pos'] = 2
        textbox.handle_input('\x7f')
        self.assertEqual(textbox.state['content'], 'Hll')
        self.assertEqual(textbox.state['cursor_pos'], 1)

        # Backspace at beginning does nothing
        textbox.state['cursor_pos'] = 0
        textbox.handle_input('\x7f')
        self.assertEqual(textbox.state['content'], 'Hll')
        self.assertEqual(textbox.state['cursor_pos'], 0)

    def test_textbox_enter_and_submit_handling(self):
        """Test enter key and submit handling."""
        handle_submit = Mock()
        textbox = TextBox(width=20, handle_submit=handle_submit)
        textbox.state['content'] = 'Test content'

        # Enter key calls submit handler
        textbox.handle_input('\r')
        handle_submit.assert_called_once_with('Test content')

        # Content remains unchanged after submit
        self.assertEqual(textbox.state['content'], 'Test content')

    def test_textbox_emacs_navigation_keybindings(self):
        """Test Emacs-style navigation keybindings."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello World'
        textbox.state['cursor_pos'] = 5

        # Ctrl+B - move backward one character
        textbox.handle_input('\x02')
        self.assertEqual(textbox.state['cursor_pos'], 4)

        # Ctrl+F - move forward one character
        textbox.handle_input('\x06')
        self.assertEqual(textbox.state['cursor_pos'], 5)

        # Ctrl+A - move to beginning of line
        textbox.handle_input('\x01')
        self.assertEqual(textbox.state['cursor_pos'], 0)

        # Ctrl+E - move to end of line
        textbox.handle_input('\x05')
        self.assertEqual(textbox.state['cursor_pos'], 11)

        # Ctrl+B at beginning does nothing
        textbox.state['cursor_pos'] = 0
        textbox.handle_input('\x02')
        self.assertEqual(textbox.state['cursor_pos'], 0)

        # Ctrl+F at end does nothing
        textbox.state['cursor_pos'] = 11
        textbox.handle_input('\x06')
        self.assertEqual(textbox.state['cursor_pos'], 11)

    def test_textbox_delete_keybinding(self):
        """Test delete keybinding (Ctrl+D)."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello'
        textbox.state['cursor_pos'] = 2

        # Ctrl+D - delete character at cursor
        textbox.handle_input('\x04')
        self.assertEqual(textbox.state['content'], 'Helo')
        self.assertEqual(textbox.state['cursor_pos'], 2)

        # Ctrl+D at end does nothing
        textbox.state['content'] = 'Hello'
        textbox.state['cursor_pos'] = 5
        textbox.handle_input('\x04')
        self.assertEqual(textbox.state['content'], 'Hello')

    def test_textbox_transpose_keybinding(self):
        """Test transpose keybinding (Ctrl+T)."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello'
        textbox.state['cursor_pos'] = 2

        # Ctrl+T - transpose characters
        textbox.handle_input('\x14')
        self.assertEqual(textbox.state['content'], 'Hlelo')
        self.assertEqual(textbox.state['cursor_pos'], 3)

    def test_textbox_kill_line_keybinding(self):
        """Test Ctrl+K kill to end of line."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello World'
        textbox.state['cursor_pos'] = 5

        # Ctrl+K - kill to end of line
        textbox.handle_input('\x0b')
        self.assertEqual(textbox.state['content'], 'Hello')
        self.assertEqual(textbox.state['cursor_pos'], 5)

    def test_textbox_multiline_navigation(self):
        """Test multiline navigation with Ctrl+N and Ctrl+P."""
        textbox = TextBox(width=5)  # Small width to test line wrapping
        textbox.state['content'] = 'Hello\nWorld\nTest'
        textbox.state['cursor_pos'] = 0

        # Ctrl+N - move to next line
        textbox.handle_input('\x0e')
        line, col = textbox.get_cursor_line_col()
        self.assertEqual(line, 1)

        # Ctrl+P - move to previous line
        textbox.handle_input('\x10')
        line, col = textbox.get_cursor_line_col()
        self.assertEqual(line, 0)

    def test_textbox_arrow_key_navigation(self):
        """Test arrow key navigation."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello\nWorld'
        textbox.state['cursor_pos'] = 5

        # Left arrow
        textbox.handle_input('\x1b[D')
        self.assertEqual(textbox.state['cursor_pos'], 4)

        # Right arrow
        textbox.handle_input('\x1b[C')
        self.assertEqual(textbox.state['cursor_pos'], 5)

        # Down arrow
        textbox.handle_input('\x1b[B')
        self.assertEqual(textbox.state['cursor_pos'], 11)

        # Up arrow
        textbox.handle_input('\x1b[A')
        self.assertEqual(textbox.state['cursor_pos'], 5)

    def test_textbox_word_navigation(self):
        """Test word navigation with Alt+F and Alt+B."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello World Test'
        textbox.state['cursor_pos'] = 0

        # Alt+F - move forward one word
        textbox.handle_input('\x1bf')
        self.assertEqual(textbox.state['cursor_pos'], 6)

        # Alt+B - move backward one word
        textbox.handle_input('\x1bb')
        self.assertEqual(textbox.state['cursor_pos'], 0)

    def test_textbox_alt_backspace_word_deletion(self):
        """Test Alt+Backspace for word deletion."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello World Test'
        textbox.state['cursor_pos'] = 12

        # Alt+Backspace - delete word
        textbox.handle_input('\x1b\x7f')
        self.assertEqual(textbox.state['content'], 'Hello Test')
        self.assertEqual(textbox.state['cursor_pos'], 6)

    def test_textbox_alt_enter_newline(self):
        """Test Alt+Enter for inserting newline."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello World'
        textbox.state['cursor_pos'] = 5

        # Alt+Enter - insert newline
        textbox.handle_input('\x1b\r')
        self.assertEqual(textbox.state['content'], 'Hello\n World')
        self.assertEqual(textbox.state['cursor_pos'], 6)

    def test_textbox_ctrl_o_insert_newline(self):
        """Test Ctrl+O for inserting newline after cursor."""
        textbox = TextBox(width=20)
        textbox.state['content'] = 'Hello'
        textbox.state['cursor_pos'] = 2

        # Ctrl+O - insert newline after cursor
        textbox.handle_input('\x0f')
        self.assertEqual(textbox.state['content'], 'Hel\nlo')

    def test_textbox_change_callback(self):
        """Test change callback is called when content changes."""
        handle_change = Mock()
        textbox = TextBox(width=20, handle_change=handle_change)

        # Change callback called on character input
        textbox.handle_input('H')
        handle_change.assert_called_once_with('H')
        handle_change.reset_mock()

        # Change callback called on backspace
        textbox.handle_input('\x7f')
        handle_change.assert_called_once_with('')
        handle_change.reset_mock()

        # Change callback not called when content doesn't change
        textbox.state['content'] = ''
        textbox.state['cursor_pos'] = 0
        textbox.handle_input('\x7f')  # Backspace at beginning
        handle_change.assert_not_called()


class TestTextBoxRendering(unittest.TestCase):
    def test_textbox_rendering_with_padding(self):
        """Test textbox renders correct size with different combinations of padding, content, and placeholder text."""
        test_cases: list[tuple[int, Spacing, str, str, str]] = [
            # (width, padding, content, placeholder, description)
            (20, 0, 'Hello', '', "No padding, with content"),
            (20, 2, 'Hello', '', "Uniform padding, with content"),
            (15, {'top': 1, 'bottom': 2, 'left': 1, 'right': 2}, 'Test', '', "Asymmetric padding, with content"),
            (20, 0, '', 'Enter text...', "No padding, with placeholder"),
            (20, 2, '', 'Enter text...', "Uniform padding, with placeholder"),
        ]
        for width, padding, content, placeholder, description in test_cases:
            with self.subTest(msg=description):
                textbox = TextBox(width=width, padding=padding, placeholder=placeholder)
                textbox.state['content'] = content
                textbox.state['cursor_pos'] = len(content)
                rendered = textbox.render([])
                lines = rendered.split('\n')
                if isinstance(padding, int):
                    expected_lines = 3 + padding * 2  # Uniform padding adds to top and bottom
                else:
                    expected_lines = 3 + padding.get('top', 0) + padding.get('bottom', 0)

                # Lines should match expected count and width
                self.assertEqual(len(lines), expected_lines)
                for line in lines:
                    self.assertEqual(ansi_len(line), width)

                # Content and placeholder should be rendered correctly
                if not content and placeholder:
                    self.assertIn(placeholder, ansi_strip(rendered))
                if content:
                    self.assertIn(content, ansi_strip(rendered))
