import unittest

from ask.ui.core.markdown_ import render_markdown
from ask.ui.core.styles import Colors, Styles
from ask.ui.theme import Theme


class TestRenderMarkdown(unittest.TestCase):
    def test_basic_formatting(self) -> None:
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
                result = render_markdown(input_text, code_color=Theme.BLUE)
                assert result == expected

    def test_nested_formatting(self) -> None:
        result = render_markdown("**bold *italic* text**", code_color=Theme.BLUE)
        assert result == f"{Styles.BOLD}bold {Styles.ITALIC}italic{Styles.ITALIC_END} text{Styles.BOLD_END}"

    def test_nested_lists(self) -> None:
        result = render_markdown("- Item 1\n  - Subitem 1.1\n  Subitem 1.1 cont\n- Item 2", code_color=Theme.BLUE)
        assert result == "• Item 1\n  • Subitem 1.1\n  Subitem 1.1 cont\n• Item 2"
        result = render_markdown("- **Item 1**:\n  - Subitem 1.1\n  - Subitem 1.2\n- **Item 2**", code_color=Theme.BLUE)
        assert result == f"• {Styles.BOLD}Item 1{Styles.BOLD_END}:\n  • Subitem 1.1\n  • Subitem 1.2\n• {Styles.BOLD}Item 2{Styles.BOLD_END}"
        result = render_markdown("- **Item 1**:\n  - Subitem 1.1\n  - Subitem 1.2\n\n- **Item 2**", code_color=Theme.BLUE)
        assert result == f"• {Styles.BOLD}Item 1{Styles.BOLD_END}:\n  • Subitem 1.1\n  • Subitem 1.2\n• {Styles.BOLD}Item 2{Styles.BOLD_END}"

    def test_html_special_characters(self) -> None:
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
                result = render_markdown(input_text, code_color=Theme.BLUE)
                assert result == expected
