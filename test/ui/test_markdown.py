import unittest

from ask.ui.core.markdown_ import render_markdown
from ask.ui.core.styles import Colors, Styles, Theme

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

    def test_html_special_characters(self):
        test_cases = [
            ("Text with & ampersand", "Text with & ampersand", "ampersand character"),
            ("Less than < and greater than >", "Less than < and greater than >", "angle brackets"),
            ("Quotes: \"double\" and 'single'", "Quotes: \"double\" and 'single'", "quote characters"),
            ("Mixed: & < > \" '", "Mixed: & < > \" '", "multiple special characters"),
            ("`Code with & < >`", f"{Colors.HEX(Theme.BLUE)}Code with & < >{Colors.END}", "special chars in code"),
            ("**Bold & italic**", f"{Styles.BOLD}Bold & italic{Styles.BOLD_END}", "special chars in bold"),
        ]

        for input_text, expected, description in test_cases:
            with self.subTest(description=description):
                result = render_markdown(input_text)
                self.assertEqual(result, expected)
