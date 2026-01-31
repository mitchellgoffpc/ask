import unittest

from ask.ui.core.styles import Colors, Styles, Wrap, ansi_strip, ansi_len, ansi_slice, ansi256, ansi16m, wrap_lines

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
            ("empty slice at start", f"{Colors.RED}hello{Colors.END}", 0, 0, ""),
            ("empty slice past end", f"{Colors.RED}hello{Colors.END}", 5, 6, ""),
            ("slice starting with color reset", f"{Colors.END}a{Colors.RED}bcd{Colors.END}", 0, 3, f"a{Colors.RED}bc{Colors.END}"),
            ("slice starting with style reset", f"{Styles.BOLD_END}a{Styles.BOLD}bcd{Styles.BOLD_END}", 0, 3, f"a{Styles.BOLD}bc{Styles.RESET}"),
            ("slice with empty ansi blocks", f"{Colors.RED}{Colors.END}a{Colors.BLUE}{Colors.END}bc{Styles.BOLD}{Styles.BOLD_END}", 0, 3, "abc"),
        ]
        for description, text, start, end, expected in test_cases:
            with self.subTest(description=description):
                result = ansi_slice(text, start, end)
                self.assertEqual(ansi_len(result), min(ansi_len(text), end) - start)
                self.assertEqual(result, expected)


class TestWrapLines(unittest.TestCase):
    def test_no_wrap(self):
        test_cases = [
            ("plain text", "Hello World", 20),
            ("single character", f"{Colors.RED}A{Colors.END}", 1),
            ("multiple lines", "line1\nline2", 5),
            ("multiple styled lines", f"{Colors.RED}line1{Colors.END}\n{Colors.BLUE}line2{Colors.END}", 5),
            ("trailing newline", "line1\nline2\n", 5)
        ]
        for description, styled_text, width in test_cases:
            with self.subTest(description=description):
                self.assertEqual(wrap_lines(styled_text, width, wrap=Wrap.EXACT), styled_text)
                self.assertEqual(wrap_lines(styled_text, width, wrap=Wrap.WORDS), styled_text)

    def test_wrap_styled_lines(self):
        test_cases = [
            ("one character short", f"{Colors.RED}line\nline2{Colors.END}", f"{Colors.RED}line{Colors.END}\n{Colors.RED}line2{Colors.END}", 5),
            ("exact fit", f"{Colors.RED}line1\nline2{Colors.END}", f"{Colors.RED}line1{Colors.END}\n{Colors.RED}line2{Colors.END}", 5),
            ("with empty line", f"{Colors.RED}line1\n\nline2{Colors.END}", f"{Colors.RED}line1{Colors.END}\n\n{Colors.RED}line2{Colors.END}", 5),
        ]
        for description, styled_text, expected, width in test_cases:
            with self.subTest(description=description):
                self.assertEqual(wrap_lines(styled_text, width, wrap=Wrap.EXACT), expected)
                self.assertEqual(wrap_lines(styled_text, width, wrap=Wrap.WORDS), expected)

    def test_wrap_exact(self):
        styled_text = f"{Colors.RED}This is a very {Styles.BOLD}long red text{Styles.BOLD_END} that should wrap{Colors.END}"
        expected_result = (
            f"{Colors.RED}This is a very {Styles.BOLD}long {Colors.END}{Styles.RESET}\n"
            f"{Styles.BOLD}{Colors.RED}red text{Styles.BOLD_END} that should{Colors.END}\n"
            f"{Colors.RED} wrap{Colors.END}")
        self.assertEqual(wrap_lines(styled_text, 20, wrap=Wrap.EXACT), expected_result)

        styled_text = f"{Colors.RED}This is:\na very long red text that should wrap.{Colors.END}"
        expected_result = (
            f"{Colors.RED}This is:{Colors.END}\n"
            f"{Colors.RED}a very long red text{Colors.END}\n"
            f"{Colors.RED} that should wrap.{Colors.END}")
        self.assertEqual(wrap_lines(styled_text, 20, wrap=Wrap.EXACT), expected_result)

    def test_wrap_words(self):
        test_cases = [
            ("simple wrap", "This is a very long line", "This is a\nvery long\nline", 10),
            ("long word break", "supercalifragilistic", "supercal\nifragili\nstic", 8),
            ("word exact length", "hello world", "hello\nworld", 5),
            ("leading whitespace", "test    space\n  a", "test \nspace\n  a", 5),
        ]
        for description, input_text, expected, width in test_cases:
            with self.subTest(description=description):
                self.assertEqual(wrap_lines(input_text, width, wrap=Wrap.WORDS), expected)
