import unittest
from ask.ui.components import Box, Text, Spacing, get_spacing_dict
from ask.ui.styles import Borders, ansi_len


class TestBoxCreation(unittest.TestCase):
    def test_box_default_props(self):
        """Test Box component creation with default props."""
        box = Box()
        self.assertIsNone(box.props['width'])
        self.assertIsNone(box.props['height'])
        self.assertEqual(box.props['margin'], 0)
        self.assertEqual(box.props['padding'], 0)
        self.assertIsNone(box.props['border_color'])
        self.assertIsNone(box.props['border_style'])
        self.assertFalse(box.leaf)

    def test_box_spacing_normalization(self):
        """Test Box spacing prop normalization from int and dict formats."""
        # Integer spacing should expand to all sides
        box = Box(margin=2, padding=1)
        self.assertEqual(box.margin, {'top': 2, 'bottom': 2, 'left': 2, 'right': 2})
        self.assertEqual(box.padding, {'top': 1, 'bottom': 1, 'left': 1, 'right': 1})

        # Dictionary spacing should be preserved
        margin: Spacing = {'top': 1, 'bottom': 2, 'left': 3, 'right': 4}
        padding: Spacing = {'top': 0, 'bottom': 1, 'left': 2, 'right': 3}
        box = Box(margin=margin, padding=padding)
        self.assertEqual(box.margin, margin)
        self.assertEqual(box.padding, padding)

        # Partial dictionary spacing should fill missing keys with 0
        box = Box(margin={'top': 5}, padding={'left': 2, 'right': 1})
        self.assertEqual(box.margin, {'top': 5, 'bottom': 0, 'left': 0, 'right': 0})
        self.assertEqual(box.padding, {'top': 0, 'bottom': 0, 'left': 2, 'right': 1})

    def test_box_with_children(self):
        """Test Box properly handles child components."""
        text1 = Text("Hello")
        text2 = Text("World")
        box = Box()[text1, text2]

        self.assertEqual(len(box.children), 2)
        self.assertIn(text1, box.children)
        self.assertIn(text2, box.children)

        rendered = box.render([child.render([], max_width=100) for child in box.children], max_width=100)
        self.assertIn("Hello", rendered)
        self.assertIn("World", rendered)


class TestBoxSizing(unittest.TestCase):
    def test_box_width_calculation(self):
        """Test box width calculation for absolute, percentage, and auto sizing."""
        test_cases = [
            # (width_prop, expected_width, content, description)
            (50, 50, [], "Absolute width"),
            (0.5, 100, [], "Percentage width (Uses max_width)"),
            (None, 5, ["Hello"], "Auto width content"),
            (None, 11, ["Hello World"], "Auto width with longer content"),
        ]

        for width_prop, expected_width, content, description in test_cases:
            with self.subTest(description=description):
                box = Box(width=width_prop, height=1)
                rendered = box.render(content, max_width=100)
                for line in rendered.split('\n'):
                    self.assertEqual(ansi_len(line), expected_width)

    def test_box_height_calculation(self):
        """Test box height calculation for absolute, percentage, and auto sizing."""
        test_cases = [
            # (height_prop, expected_height, content, description)
            (20, 20, [], "Absolute height"),
            (None, 2, ["Line1", "Line2"], "Auto height"),
        ]

        for height_prop, expected_height, content, description in test_cases:
            with self.subTest(description=description):
                box = Box(height=height_prop)
                rendered = box.render(content, max_width=100)
                self.assertEqual(len(rendered.split('\n')), expected_height)


class TestBoxRendering(unittest.TestCase):
    def test_box_without_borders(self):
        """Test Box rendering with border_style=None."""
        box = Box(width=10, border_style=None)
        rendered = box.render(["Test"], max_width=10)
        lines = rendered.split('\n')

        # There should be no borders, just the content
        self.assertEqual(len(lines), 1)
        for line in lines:
            self.assertEqual(ansi_len(line), 10)

    def test_box_content_wrapping(self):
        """Test Box content handling with wrapping and overflow scenarios."""
        # Multiline content should wrap correctly
        box = Box(width=15)
        content = ["Line 1\nLine 2", "Another line"]
        lines = box.render(content, max_width=100).split('\n')
        self.assertEqual(len(lines), 3)
        self.assertIn("Line 1", lines[0])
        self.assertIn("Line 2", lines[1])
        self.assertIn("Another line", lines[2])

        # Long lines should wrap to fit within the box width
        box = Box(width=10)
        rendered = box.render(["This is a very long line that exceeds box width"], max_width=10)
        lines = rendered.split('\n')
        for line in lines:
            self.assertLessEqual(ansi_len(line), 10)

    def test_box_spacing_rendering(self):
        """Test Box rendering with various margin and padding configurations."""
        test_cases: list[tuple[Spacing, Spacing, str]] = [
            # (margin, padding, description)
            (1, 1, "symmetric spacing"),
            ({'top': 2, 'bottom': 1, 'left': 1, 'right': 2},
             {'top': 1, 'bottom': 2, 'left': 2, 'right': 1}, "asymmetric spacing"),
            ({'top': 1}, {'right': 2}, "partial spacing"),
            (2, {'top': 1, 'bottom': 0}, "mixed int/dict spacing"),
        ]

        for margin, padding, description in test_cases:
            with self.subTest(description=description):
                box = Box(width=20, margin=margin, padding=padding, border_style=Borders.ROUND)
                lines = box.render(["Test"], max_width=100).split('\n')

                # Margin should create empty lines at top/bottom and spaces at left/right
                margin_dict = get_spacing_dict(margin)
                for i in range(margin_dict['top']):
                    self.assertEqual(lines[i], " " * 20)
                for i in range(1, margin_dict['bottom'] + 1):
                    self.assertEqual(lines[-i], " " * 20)
                for line in lines[margin_dict['top']:len(lines)-margin_dict['bottom']]:
                    self.assertTrue(line.startswith(" " * margin_dict['left']))
                    self.assertTrue(line.endswith(" " * margin_dict['right']))

                # Borders should be present
                border_top_idx = margin_dict['top']
                border_bottom_idx = len(lines) - margin_dict['bottom'] - 1
                top_line = lines[border_top_idx].strip()
                bottom_line = lines[border_bottom_idx].strip()
                self.assertTrue(top_line.startswith('╭') and top_line.endswith('╮'))
                self.assertTrue(bottom_line.startswith('╰') and bottom_line.endswith('╯'))

                # Content should be rendered in the correct position
                padding_dict = get_spacing_dict(padding)
                content_line_idx = border_top_idx + 1 + padding_dict['top']
                content_line = lines[content_line_idx]
                expected_content_idx = margin_dict['left'] + 1 + padding_dict['left']
                self.assertIn("Test", content_line)
                self.assertEqual(content_line.index("Test"), expected_content_idx)
