import unittest
from unittest.mock import Mock

from ask.ui.core.components import Box, Text
from ask.ui.core.layout import layout
from ask.ui.core.render import render
from ask.ui.core.styles import Styles, Wrap
from ask.ui.core.textbox import TextBox, TextBoxController
from ask.ui.core.tree import ElementTree, mount, update


def create_tree(textbox: TextBox) -> tuple[ElementTree, Box, TextBoxController]:
    root = Box()[textbox]
    tree = ElementTree(root)
    mount(tree, root)
    assert isinstance(textbox.controller, TextBoxController)
    return tree, root, textbox.controller

class TestTextBoxWrapping(unittest.TestCase):
    def test_textbox_wrapping_rendering(self) -> None:
        test_cases = [
            ("empty text", "", 0, 10, Wrap.EXACT, Styles.inverse(' ')),
            ("cursor at start", "Hello", 0, 10, Wrap.EXACT, Styles.inverse('H') + "ello"),
            ("cursor in middle", "Hello", 2, 10, Wrap.EXACT, "He" + Styles.inverse('l') + "lo"),
            ("cursor at end", "Hello", 5, 10, Wrap.EXACT, "Hello" + Styles.inverse(' ')),
            ("exact wrap at width boundary", "12345", 5, 5, Wrap.EXACT, "12345\n" + Styles.inverse(' ')),
            ("exact wrap cursor at line end", "1234567890", 5, 5, Wrap.EXACT, "12345\n" + Styles.inverse('6') + "7890"),
            ("exact wrap cursor in second line", "1234567890", 7, 5, Wrap.EXACT, "12345\n67" + Styles.inverse('8') + "90"),
            ("exact wrap with newline", "123\n456", 4, 10, Wrap.EXACT, "123 \n" + Styles.inverse('4') + "56"),
            ("word wrap no break needed", "Hello", 2, 10, Wrap.WORDS, "He" + Styles.inverse('l') + "lo"),
            ("word wrap at space", "Hello World", 6, 6, Wrap.WORDS, "Hello \n" + Styles.inverse('W') + "orld"),
            ("word wrap at space + cursor, ", "Hello World", 5, 6, Wrap.WORDS, "Hello" + Styles.inverse(' ') + "\nWorld"),
            ("word wrap at cursor before space", "At the ball", 6, 6, Wrap.WORDS, "At \nthe" + Styles.inverse(' ') + "\nball"),
            ("word wrap, cursor past end", "Hello    ", 8, 6, Wrap.WORDS, "Hello" + Styles.inverse(' ')),
            ("word wrap long word breaks", "Supercalifragilistic", 10, 10, Wrap.WORDS, "Supercali\nf" + Styles.inverse('r') + "agilist\nic"),
            ("cursor right after newline", "Hello\nWorld", 6, 10, Wrap.EXACT, "Hello \n" + Styles.inverse('W') + "orld"),
            ("exact wrap multiple lines cursor end", "123456789", 9, 5, Wrap.EXACT, "12345\n6789" + Styles.inverse(' ')),
            ("word wrap trailing spaces", "Hi       World", 5, 6, Wrap.WORDS, "Hi   " + Styles.inverse(' ') + "\nWorld"),
            ("word wrap trailing spaces, cursor past end", "Hi       World", 7, 6, Wrap.WORDS, "Hi   " + Styles.inverse(' ') + "\nWorld"),
        ]

        for description, text, cursor_pos, width, wrap, expected_text in test_cases:
            with self.subTest(description=description):
                textbox = TextBoxController(TextBox(width=width, wrap=wrap))
                textbox._text = text
                textbox._cursor_pos = cursor_pos
                text_elem = textbox.contents()[0]
                assert isinstance(text_elem, Text)
                self.assertEqual(text_elem.wrapped(width), expected_text,  f"Failed: {description}\nText: {repr(text)}\nCursor: {cursor_pos}\nWidth: {width}")

    def test_textbox_width_limit(self) -> None:
        tree, root, textbox = create_tree(TextBox(width=1.0, wrap=Wrap.WORDS))
        textbox._text = "123456789     "
        textbox._cursor_pos = 12
        update(tree, textbox)
        layout(tree, root, available_width=10)
        self.assertEqual(render(tree, root), '123456789' + Styles.inverse(' '))


class TestTextBoxInputHandling(unittest.TestCase):
    def test_textbox_basic_text_editing(self) -> None:
        test_cases = [
            ("insert at end", "", 0, ["A", "B"], "AB", 2),
            ("insert in middle", "AB", 1, ["X"], "AXB", 2),
            ("backspace at end", "Hello", 5, ["\x7f"], "Hell", 4),
            ("backspace in middle", "Hello", 2, ["\x7f"], "Hllo", 1),
            ("backspace at start", "Hello", 0, ["\x7f"], "Hello", 0),
            ("backspace word (Alt+Backspace)", "Hi Hello World", 14, ["\x1b\x7f"], "Hi Hello ", 9),
            ("delete character at cursor (Ctrl+D)", "Hello", 2, ["\x04"], "Helo", 2),
            ("delete at end (Ctrl+D)", "Hello", 5, ["\x04"], "Hello", 5),
            ("delete word (Alt+D)", "Hi Hello World", 2, ["\x1bd"], "Hi World", 2),
            ("transpose characters (Ctrl+T)", "Hello", 2, ["\x14"], "Hlelo", 3),
            ("transpose at end no-op (Ctrl+T)", "Hello", 5, ["\x14"], "Hello", 5),
            ("insert newline after cursor (Ctrl+O)", "Hello", 2, ["\x0f"], "He\nllo", 2),
            ("insert newline at cursor (Alt+Enter)", "Hello World", 5, ["\x1b\r"], "Hello\n World", 6),
        ]
        for description, initial_text, initial_cursor, inputs, expected_text, expected_cursor in test_cases:
            with self.subTest(description=description):
                textbox = TextBoxController(TextBox(width=20))
                textbox._text = initial_text
                textbox._cursor_pos = initial_cursor
                for ch in inputs:
                    textbox.handle_input(ch)
                self.assertEqual(textbox.text, expected_text)
                self.assertEqual(textbox.cursor_pos, expected_cursor)

    def test_textbox_navigation_keybindings(self) -> None:
        test_cases = [
            ("move backward one character (Ctrl+B / left arrow)", "Hello World", 5, ["\x02", "\x1b[D"], 4),
            ("move forward one character (Ctrl+F / right arrow)", "Hello World", 4, ["\x06", "\x1b[C"], 5),
            ("move to next line (Ctrl+N / down arrow)", "Hello\nWorld\nTest", 0, ["\x0e", "\x1b[B"], 6),
            ("move to previous line (Ctrl+P / up arrow)", "Hello\nWorld\nTest", 12, ["\x10", "\x1b[A"], 6),
            ("move to start of line (Ctrl+A)", "Hello\nWorld", 8, ["\x01"], 6),
            ("move to end of line (Ctrl+E)", "Hello\nWorld", 2, ["\x05"], 5),
            ("move forward one word (Alt+F)", "Hello World Test", 0, ["\x1bf"], 6),
            ("move backward one word (Alt+B)", "Hello World Test", 11, ["\x1bb"], 6),
            ("move back at start no-op", "Hello", 0, ["\x02", "\x1b[D"], 0),
            ("move forward at end no-op", "Hello", 5, ["\x06", "\x1b[C"], 5),
            ("move to start at start no-op", "Hello\nWorld", 0, ["\x01"], 0),
            ("move to end at end no-op", "Hello\nWorld", 11, ["\x05"], 11),
        ]
        for description, initial_text, initial_cursor, inputs, expected_cursor in test_cases:
            for ch in inputs:
                with self.subTest(description=description, input=ch):
                    tree, root, textbox = create_tree(TextBox(width=20))
                    textbox._text = initial_text
                    textbox._cursor_pos = initial_cursor
                    layout(tree, root)
                    textbox.handle_input(ch)
                    self.assertEqual(textbox.text, initial_text)
                    self.assertEqual(textbox.cursor_pos, expected_cursor)

    def test_textbox_history_paging_keybindings(self) -> None:
        test_cases = [
            ("move to newer history entry (page down)", "first", 5, ["\x1b[5~", "\x0e", "\x1b[B"], "second", 6, ["first", "second", "third"], 0),
            ("move to older history entry (page up)", "third", 5, ["\x1b[6~", "\x10", "\x1b[A"], "second", 6, ["first", "second", "third"], 2),
            ("page up at oldest entry no-op", "first", 5, ["\x1b[6~"], "first", 5, ["first", "second", "third"], 0),
            ("page down at newest entry no-op", "third", 5, ["\x1b[5~"], "third", 5, ["first", "second", "third"], 2),
            ("move to previous line no page up", "line1\nline2\nline3", 12, ["\x10", "\x1b[A"], "line1\nline2\nline3", 6, ["first", "second"], 1),
            ("move to next line no page down", "line1\nline2\nline3", 0, ["\x0e", "\x1b[B"], "line1\nline2\nline3", 6, ["first", "second"], 0),
        ]
        for description, initial_text, initial_cursor, inputs, expected_text, expected_cursor, history, history_idx in test_cases:
            for ch in inputs:
                with self.subTest(description=description, input=ch):
                    tree, root, textbox = create_tree(TextBox(width=20))
                    textbox._text = initial_text
                    textbox._cursor_pos = initial_cursor
                    textbox.history = history
                    textbox.history_idx = history_idx
                    layout(tree, root)
                    textbox.handle_input(ch)
                    self.assertEqual(textbox.text, expected_text)
                    self.assertEqual(textbox.cursor_pos, expected_cursor)

    def test_textbox_kill_yank_and_mark_keybindings(self) -> None:
        test_cases = [
            ("set mark (Ctrl+Space)", "Hello", 2, "\x00", "Hello", 2, None, 2, None, None),
            ("unset mark (Ctrl+G)", "Hello", 2, "\x07", "Hello", 2, 1, None, None, None),
            ("kill to end of line (Ctrl+K)", "Hello World", 5, "\x0b", "Hello", 5, None, None, None, " World"),
            ("kill region (Ctrl+W)", "Hello", 4, "\x17", "Ho", 1, 1, None, None, "ell"),
            ("yank (Ctrl+Y)", "Ho", 1, "\x19", "Hello", 4, None, None, "ell", None),
        ]
        for description, initial_text, initial_cursor, inputs, expected_text, expected_cursor, mark, expected_mark, kill_buf, expected_kill_buf in test_cases:
            with self.subTest(description=description):
                textbox = TextBoxController(TextBox(width=20))
                textbox._text = initial_text
                textbox._cursor_pos = initial_cursor
                if mark is not None:
                    textbox.mark = mark
                if kill_buf is not None:
                    textbox.kill_buffer = kill_buf
                textbox.handle_input(inputs)
                self.assertEqual(textbox.text, expected_text)
                self.assertEqual(textbox.cursor_pos, expected_cursor)
                if expected_mark is not None:
                    self.assertEqual(textbox.mark, expected_mark)
                if expected_kill_buf is not None:
                    self.assertEqual(textbox.kill_buffer, expected_kill_buf)

    def test_textbox_change_callback(self) -> None:
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
        textbox.handle_input('\x7f')
        handle_change.assert_not_called()

    def test_textbox_enter_and_submit_handling(self) -> None:
        handle_submit = Mock()
        textbox = TextBoxController(TextBox(width=20, handle_submit=handle_submit))
        textbox._text = 'Test content'

        # Enter key calls submit handler
        textbox.handle_input('\r')
        handle_submit.assert_called_once_with('Test content')
        self.assertEqual(textbox.text, 'Test content')
