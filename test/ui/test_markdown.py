import unittest
from ask.ui.markdown_ import render_markdown
from ask.ui.styles import Colors, Styles, Theme


class TestRenderMarkdown(unittest.TestCase):
    def test_basic_formatting(self):
        test_cases = [
            ('plain text', 'plain text', 'plain text'),
            ("**bold text**", f"{Styles.BOLD}bold text{Styles.BOLD_END}", "bold formatting"),
            ("*italic text*", f"{Styles.ITALIC}italic text{Styles.ITALIC_END}", "italic formatting"),
            ("`code snippet`", f"{Colors.HEX(Theme.BLUE)}code snippet{Colors.END}", "inline code formatting"),
            ("- list item", "• list item", "list item formatting"),
            ("# Heading", f"{Styles.BOLD}Heading{Styles.BOLD_END}", "heading formatting"),
            ("```\n*hello*\n```", "*hello*", "fenced code block"),
        ]

        for input_text, expected, description in test_cases:
            with self.subTest(description=description):
                result = render_markdown(input_text)
                self.assertEqual(result, expected)

    def test_nested_formatting(self):
        result = render_markdown("**bold *italic* text**")
        self.assertEqual(result, f"{Styles.BOLD}bold {Styles.ITALIC}italic{Styles.ITALIC_END} text{Styles.BOLD_END}")

    def test_nested_lists(self):
        result = render_markdown("* Item 1\n  * Subitem 1.1\n  Another item\n* Item 2")
        self.assertEqual(result, "• Item 1\n  • Subitem 1.1\n  Another item\n• Item 2")
