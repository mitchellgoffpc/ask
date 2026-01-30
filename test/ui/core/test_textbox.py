import unittest
from unittest.mock import Mock

from ask.ui.core.components import Box
from ask.ui.core.layout import layout
from ask.ui.core.tree import ElementTree, mount, update
from ask.ui.core.textbox import TextBox, TextBoxController

def create_tree(textbox: TextBox) -> tuple[ElementTree, Box, TextBoxController]:
    root = Box()[textbox]
    tree = ElementTree(root)
    mount(tree, root)

    assert isinstance(textbox.controller, TextBoxController)
    return tree, root, textbox.controller

class TestTextBoxWrapping(unittest.TestCase):
    def test_textbox_line_wrapping_methods(self):
        """Test line wrapping and cursor position calculation methods."""
        tree, root, textbox = create_tree(TextBox(width=5))
        textbox._text = 'Hello World'
        textbox._cursor_pos = 8
        update(tree, root)
        layout(tree, root)

        # Test cursor line/col calculation
        line, col = textbox.get_cursor_line_col()
        self.assertEqual(line, 1)
        self.assertEqual(col, 3)

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
        textbox = TextBoxController(TextBox(width=20))

        # Insert at end
        textbox.handle_input('A')
        textbox.handle_input('B')
        self.assertEqual(textbox.text, 'AB')
        self.assertEqual(textbox.cursor_pos, 2)

        # Insert in the middle
        textbox._cursor_pos = 1
        textbox.handle_input('X')
        self.assertEqual(textbox.text, 'AXB')
        self.assertEqual(textbox.cursor_pos, 2)

    def test_textbox_backspace_handling(self):
        """Test backspace handling."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello'
        textbox._cursor_pos = 5

        # Backspace removes character before cursor
        textbox.handle_input('\x7f')
        self.assertEqual(textbox.text, 'Hell')
        self.assertEqual(textbox.cursor_pos, 4)

        # Backspace in the middle removes character before cursor
        textbox._cursor_pos = 2
        textbox.handle_input('\x7f')
        self.assertEqual(textbox.text, 'Hll')
        self.assertEqual(textbox.cursor_pos, 1)

        # Backspace at beginning does nothing
        textbox._cursor_pos = 0
        textbox.handle_input('\x7f')
        self.assertEqual(textbox.text, 'Hll')
        self.assertEqual(textbox.cursor_pos, 0)

    def test_textbox_enter_and_submit_handling(self):
        """Test enter key and submit handling."""
        handle_submit = Mock()
        textbox = TextBoxController(TextBox(width=20, handle_submit=handle_submit))
        textbox._text = 'Test content'

        # Enter key calls submit handler
        textbox.handle_input('\r')
        handle_submit.assert_called_once_with('Test content')

        # Content remains unchanged after submit
        self.assertEqual(textbox.text, 'Test content')

    def test_textbox_emacs_navigation_keybindings(self):
        """Test Emacs-style navigation keybindings."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello World'
        textbox._cursor_pos = 5

        # Ctrl+B - move backward one character
        textbox.handle_input('\x02')
        self.assertEqual(textbox.cursor_pos, 4)

        # Ctrl+F - move forward one character
        textbox.handle_input('\x06')
        self.assertEqual(textbox.cursor_pos, 5)

        # Ctrl+A - move to beginning of line
        textbox.handle_input('\x01')
        self.assertEqual(textbox.cursor_pos, 0)

        # Ctrl+E - move to end of line
        textbox.handle_input('\x05')
        self.assertEqual(textbox.cursor_pos, 11)

        # Ctrl+B at beginning does nothing
        textbox._cursor_pos = 0
        textbox.handle_input('\x02')
        self.assertEqual(textbox.cursor_pos, 0)

        # Ctrl+F at end does nothing
        textbox._cursor_pos = 11
        textbox.handle_input('\x06')
        self.assertEqual(textbox.cursor_pos, 11)

    def test_textbox_delete_keybinding(self):
        """Test delete keybinding (Ctrl+D)."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello'
        textbox._cursor_pos = 2

        # Ctrl+D - delete character at cursor
        textbox.handle_input('\x04')
        self.assertEqual(textbox.text, 'Helo')
        self.assertEqual(textbox.cursor_pos, 2)

        # Ctrl+D at end does nothing
        textbox._text = 'Hello'
        textbox._cursor_pos = 5
        textbox.handle_input('\x04')
        self.assertEqual(textbox.text, 'Hello')

    def test_textbox_transpose_keybinding(self):
        """Test transpose keybinding (Ctrl+T)."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello'
        textbox._cursor_pos = 2

        # Ctrl+T - transpose characters
        textbox.handle_input('\x14')
        self.assertEqual(textbox.text, 'Hlelo')
        self.assertEqual(textbox.cursor_pos, 3)

    def test_textbox_kill_line_keybinding(self):
        """Test Ctrl+K kill to end of line."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello World'
        textbox._cursor_pos = 5

        # Ctrl+K - kill to end of line
        textbox.handle_input('\x0b')
        self.assertEqual(textbox.text, 'Hello')
        self.assertEqual(textbox.cursor_pos, 5)

    def test_textbox_multiline_navigation(self):
        """Test multiline navigation with Ctrl+N and Ctrl+P."""
        tree, root, textbox = create_tree(TextBox(width=5))  # Small width to test line wrapping
        textbox._text = 'Hello\nWorld\nTest'
        layout(tree, root)

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
        tree, root, textbox = create_tree(TextBox(width=20))
        textbox._text = 'Hello\nWorld'
        textbox._cursor_pos = 5
        layout(tree, root)

        # Left arrow
        textbox.handle_input('\x1b[D')
        self.assertEqual(textbox.cursor_pos, 4)

        # Right arrow
        textbox.handle_input('\x1b[C')
        self.assertEqual(textbox.cursor_pos, 5)

        # Down arrow
        textbox.handle_input('\x1b[B')
        self.assertEqual(textbox.cursor_pos, 11)

        # Up arrow
        textbox.handle_input('\x1b[A')
        self.assertEqual(textbox.cursor_pos, 5)

    def test_textbox_word_navigation(self):
        """Test word navigation with Alt+F and Alt+B."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello World Test'
        textbox._cursor_pos = 0

        # Alt+F - move forward one word
        textbox.handle_input('\x1bf')
        self.assertEqual(textbox.cursor_pos, 6)

        # Alt+B - move backward one word
        textbox.handle_input('\x1bb')
        self.assertEqual(textbox.cursor_pos, 0)

    def test_textbox_alt_backspace_word_deletion(self):
        """Test Alt+Backspace for word deletion."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello World Test'
        textbox._cursor_pos = 12

        # Alt+Backspace - delete word
        textbox.handle_input('\x1b\x7f')
        self.assertEqual(textbox.text, 'Hello Test')
        self.assertEqual(textbox.cursor_pos, 6)

    def test_textbox_alt_enter_newline(self):
        """Test Alt+Enter for inserting newline."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello World'
        textbox._cursor_pos = 5

        # Alt+Enter - insert newline
        textbox.handle_input('\x1b\r')
        self.assertEqual(textbox.text, 'Hello\n World')
        self.assertEqual(textbox.cursor_pos, 6)

    def test_textbox_ctrl_o_insert_newline(self):
        """Test Ctrl+O for inserting newline after cursor."""
        textbox = TextBoxController(TextBox(width=20))
        textbox._text = 'Hello'
        textbox._cursor_pos = 2

        # Ctrl+O - insert newline after cursor
        textbox.handle_input('\x0f')
        self.assertEqual(textbox.text, 'He\nllo')

    def test_textbox_change_callback(self):
        """Test change callback is called when content changes."""
        handle_change = Mock()
        textbox = TextBoxController(TextBox(width=20, handle_change=handle_change))

        # Change callback called on character input
        textbox.handle_input('H')
        handle_change.assert_called_once_with('H')
        handle_change.reset_mock()

        # Change callback called on backspace
        textbox.handle_input('\x7f')
        handle_change.assert_called_once_with('')
        handle_change.reset_mock()

        # Change callback not called when content doesn't change
        textbox._text = ''
        textbox._cursor_pos = 0
        textbox.handle_input('\x7f')  # Backspace at beginning
        handle_change.assert_not_called()
