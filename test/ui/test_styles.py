import unittest
from ask.ui.styles import Colors, Styles, ansi_strip, ansi_len, ansi_slice, ansi256, ansi16m, wrap_lines


class TestAnsiStrip(unittest.TestCase):
    def test_ansi_strip(self):
        test_cases = [
            ("plain text", "plain text"),
            (f"foo{Colors.RED}bar{Colors.END}baz", "foobarbaz"),
            (f"{Styles.BOLD}[{Colors.BLUE}hello world{Colors.END}]{Styles.BOLD_END}", "[hello world]"),
        ]
        for input_text, expected in test_cases:
            self.assertEqual(ansi_strip(input_text), expected)


class TestAnsiLen(unittest.TestCase):
    def test_ansi_len(self):
        test_cases = [
            ("plain text", 10),
            (f"foo{Colors.RED}bar{Colors.END}baz", 9),
            (f"{Styles.BOLD}[{Colors.BLUE}hello world{Colors.END}]{Styles.BOLD_END}", 13),
        ]
        for input_text, expected in test_cases:
            self.assertEqual(ansi_len(input_text), expected)


class TestAnsiSlice(unittest.TestCase):
    def test_ansi_slice(self):
        test_cases = [
            ("basic slice", "hello world", 0, 5, "hello"),
            ("basic slice end", "hello world", 6, 11, "world"),
            ("ansi16 colors", f"{Colors.ansi('hello', Colors.RED)} world", 0, 5, f"{Colors.RED}hello{Colors.END}"),
            ("ansi256 colors", f"{ansi256(196)}hello{Colors.END} world", 0, 5, f"{ansi256(196)}hello{Colors.END}"),
            ("ansi16m colors", f"{ansi16m(255, 0, 0)}hello{Colors.END} world", 0, 5, f"{ansi16m(255, 0, 0)}hello{Colors.END}"),
            ("background colors", f"{Colors.BG_RED}hello{Colors.BG_END} world", 0, 5, f"{Colors.BG_RED}hello{Colors.BG_END}"),
            ("styles", f"{Styles.BOLD}hello{Styles.BOLD_END} world", 0, 5, f"{Styles.BOLD}hello{Styles.RESET}"),
            ("slice inside styled section", f"{Colors.RED}hello world{Colors.END}", 2, 8, f"{Colors.RED}llo wo{Colors.END}"),
            ("slice across styled sections", f"{Colors.RED}hello{Colors.END} {Colors.BLUE}world{Colors.END}", 3, 8,
                                             f"{Colors.RED}lo{Colors.END} {Colors.BLUE}wo{Colors.END}"),
            ("multiline slice", f"{Colors.RED}hello\nworld{Colors.END}", 3, 9, f"{Colors.RED}lo\nwor{Colors.END}"),
        ]
        for description, text, start, end, expected in test_cases:
            with self.subTest(description=description):
                result = ansi_slice(text, start, end)
                self.assertEqual(ansi_len(result), end - start)
                self.assertEqual(result, expected)


class TestWrapLines(unittest.TestCase):
    def test_wrap_lines(self):
        styled_text = f"{Colors.RED}This is a very {Styles.BOLD}long red text{Styles.BOLD_END} that should wrap{Colors.END}"
        lines = wrap_lines(styled_text, 20).split('\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(ansi_len(lines[0]), 20)
        self.assertEqual(ansi_len(lines[1]), 20)
        self.assertEqual(lines[0], f"{Colors.RED}This is a very {Styles.BOLD}long {Colors.END}{Styles.RESET}")
        self.assertEqual(lines[1], f"{Styles.BOLD}{Colors.RED}red text{Styles.BOLD_END} that should{Colors.END}")
        self.assertEqual(lines[2], f"{Colors.RED} wrap{Colors.END}")

    def test_wrap_lines_with_multiple_paragraphs(self):
        styled_text = f"{Colors.RED}This is:\na very long red text that should wrap.{Colors.END}"
        lines = wrap_lines(styled_text, 20).split('\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(ansi_len(lines[0]), 8)
        self.assertEqual(ansi_len(lines[1]), 20)
        self.assertEqual(lines[0], f"{Colors.RED}This is:{Colors.END}")
        self.assertEqual(lines[1], f"{Colors.RED}a very long red text{Colors.END}")
        self.assertEqual(lines[2], f"{Colors.RED} that should wrap.{Colors.END}")
