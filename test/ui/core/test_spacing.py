import unittest
from typing import get_args

from ask.ui.core.components import Box, Side, Spacing, get_spacing_dict
from ask.ui.core.styles import Axis, Borders, BorderStyle, Colors, ansi_len
from ask.ui.core.render import apply_sizing, apply_spacing, apply_borders, apply_boxing

class TestApplySizing(unittest.TestCase):
    def test_apply_sizing_truncation_and_padding(self):
        """Test apply_sizing truncates oversized content and pads undersized content."""
        test_cases = [
            ("Hello World", 5, 3, "Hello\n     \n     "),
            ("Short", 10, 2, "Short     \n          "),
            ("Line1\nLine2\nLine3\nLine4", 6, 2, "Line1 \nLine2 "),
            ("A\nBB\nCCC", 2, 4, "A \nBB\nCC\n  "),
            ("", 3, 2, "   \n   "),
        ]

        for content, width, height, expected in test_cases:
            with self.subTest(content=content, width=width, height=height):
                result = apply_sizing(content, width, height)
                self.assertEqual(result, expected)


class TestApplySpacing(unittest.TestCase):
    def test_apply_no_spacing(self):
        """Test that apply_spacing returns content unchanged when no spacing is specified."""
        self.assertEqual(apply_spacing("Hello", {'top': 0, 'bottom': 0, 'left': 0, 'right': 0}), "Hello")

    def test_apply_spacing_with_invalid_content(self):
        """Test that apply_spacing raises an error if content lines have mismatched widths."""
        with self.assertRaises(AssertionError):
            apply_spacing("Short line\nlonger line", {'top': 0, 'bottom': 0, 'left': 0, 'right': 0})

    def test_apply_spacing(self):
        """Test apply_spacing function with various spacing configurations."""
        test_cases: list[tuple[str, dict[Side, int], str]] = [
            # (content, spacing_dict, description)
            ("Hello", {'top': 1, 'bottom': 1, 'left': 1, 'right': 1}, "uniform spacing"),
            ("Hello", {'top': 2, 'bottom': 0, 'left': 3, 'right': 1}, "asymmetric spacing"),
            ("Line1\nLine2", {'top': 1, 'bottom': 1, 'left': 2, 'right': 2}, "multiline content"),
            ("", {'top': 1, 'bottom': 1, 'left': 1, 'right': 1}, "empty content"),
        ]

        for content, spacing, description in test_cases:
            with self.subTest(description=description):
                lines = apply_spacing(content, spacing).split('\n')
                expected_width = ansi_len(content.split('\n')[0]) + spacing['left'] + spacing['right']

                # Check top/bottom spacing
                for line in lines[:spacing['top']]:
                    self.assertEqual(line, ' ' * expected_width)
                for line in lines[len(lines) - spacing['bottom']:]:
                    self.assertEqual(line, ' ' * expected_width)

                # Check left/right spacing
                for i, content_line in enumerate(content.split('\n')):
                    self.assertEqual(lines[spacing['top'] + i], ' ' * spacing['left'] + content_line + ' ' * spacing['right'])


class TestApplyBorders(unittest.TestCase):
    def test_apply_no_border(self):
        """Test that apply_borders returns content unchanged when no border is specified."""
        self.assertEqual(apply_borders("Hello", 5, set(), Borders.ROUND, None), "Hello")

    def test_apply_borders_with_invalid_content(self):
        """Test that apply_borders raises an error if content lines do not match the specified width."""
        with self.assertRaises(AssertionError):
            apply_borders("Short line\nlonger line", 10, {'top', 'bottom', 'left', 'right'}, Borders.SINGLE, None)

    def test_apply_border_sides(self):
        """Test apply_borders function with different border sides."""
        content = "Hello\nWorld"
        width = 5
        border_style = Borders.SINGLE

        result = apply_borders(content, width, {'top'}, border_style, None)
        self.assertEqual(result, border_style.top * width + '\n' + content)

        lines = apply_borders(content, width, {'left'}, border_style, None).split('\n')
        self.assertEqual(lines[0], border_style.left + "Hello")
        self.assertEqual(lines[1], border_style.left + "World")

        lines = apply_borders(content, width, {'bottom', 'right'}, border_style, None).split('\n')
        self.assertEqual(lines[0], "Hello" + border_style.right)
        self.assertEqual(lines[1], "World" + border_style.right)
        self.assertEqual(lines[2], border_style.bottom * width + border_style.bottom_right)

    def test_apply_border_styles(self):
        """Test apply_borders function with different border styles."""
        test_cases = [
            # (content, width, border_style, border_color, description)
            ("Hello", 5, Borders.SINGLE, None, "single border no color"),
            ("Hello", 5, Borders.ROUND, Colors.HEX("#FF0000"), "round border with color"),
            ("Line1\nLine2", 5, Borders.DOUBLE, None, "multiline with double border"),
            ("", 10, Borders.BOLD, None, "empty content with bold border"),
        ]

        for content, width, border_style, border_color, description in test_cases:
            with self.subTest(description=description):
                lines = apply_borders(content, width, {'top', 'bottom', 'left', 'right'}, border_style, border_color).split('\n')

                # Check line and column counts
                content_lines = content.split('\n') if content else []
                self.assertEqual(len(lines), len(content_lines) + 2)
                for line in lines[1:-1]:
                    self.assertEqual(ansi_len(line), width + 2)

                # Check top and bottom borders
                expected_border = border_style.top_left + border_style.top * width + border_style.top_right
                self.assertEqual(lines[0], Colors.ansi(expected_border, border_color or ''))
                expected_border = border_style.bottom_left + border_style.bottom * width + border_style.bottom_right
                self.assertEqual(lines[-1], Colors.ansi(expected_border, border_color or ''))

                # Check side borders
                for line in lines[1:-1]:
                    self.assertTrue(line.startswith(Colors.ansi(border_style.left, border_color or '')))
                    self.assertTrue(line.endswith(Colors.ansi(border_style.right, border_color or '')))


class TestApplyBoxing(unittest.TestCase):
    def test_apply_boxing_with_borders_and_spacing(self):
        """Test apply_boxing with borders, padding, and margin combinations."""
        content = "Hello World"
        test_cases: list[tuple[Spacing, Spacing, tuple[Side, ...], BorderStyle, str]] = [
            # (padding, margin, border_style, description)
            (0, 1, get_args(Side), Borders.SINGLE, "with margin, and single border"),
            (0, {'top': 2, 'bottom': 1}, get_args(Side), Borders.ROUND, "asymmetric spacing with round border"),
            (0, {'left': 2, 'right': 2}, get_args(Side), Borders.DOUBLE, "horizontal margin, double border"),
            (0, 0, (), Borders.ROUND, "padding only, no border or margin"),
        ]

        for padding, margin, border, border_style, description in test_cases:
            with self.subTest(description=description):
                box = Box(width=20, height=3, padding=padding, margin=margin, border=border, border_style=border_style)
                lines = apply_boxing(content, 20 - box.chrome(Axis.HORIZONTAL), 3, box).split('\n')

                # Check top/bottom margin
                margin_dict = get_spacing_dict(margin)
                for line in lines[:margin_dict['top']]:
                    self.assertEqual(line, ' ' * 20)
                for line in lines[len(lines) - margin_dict['bottom']:]:
                    self.assertEqual(line, ' ' * 20)

                # Check left/right margin
                for line in lines:
                    self.assertTrue(line.startswith(' ' * margin_dict['left']))
                    self.assertTrue(line.endswith(' ' * margin_dict['right']))

                # Check border presence if specified
                if border:
                    self.assertTrue(any(
                        border_style.top_left in line or border_style.top_right in line or
                        border_style.bottom_left in line or border_style.bottom_right in line
                        for line in lines
                    ))
