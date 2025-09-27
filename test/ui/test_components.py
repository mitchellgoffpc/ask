import unittest
from ask.ui.core.components import Box, Text


class TestBox(unittest.TestCase):
    def test_box_with_children(self):
        """Test Box properly handles child components."""
        text1 = Text("Hello")
        text2 = Text("World")
        box = Box()[text1, text2]

        self.assertEqual(len(box.children), 2)
        self.assertIn(text1, box.children)
        self.assertIn(text2, box.children)

        rendered = box.render([child.render([], max_width=100) for child in box.children if child], max_width=100)
        self.assertIn("Hello", rendered)
        self.assertIn("World", rendered)


class TestText(unittest.TestCase):
    def test_text_rendering(self):
        """Test Text component rendering with various margin configurations."""
        # No spacing
        text_comp = Text("Hello World")
        rendered = text_comp.render([], max_width=100)
        self.assertEqual(rendered, "Hello World")

        # Multiline with margin and padding
        text_comp = Text("Hello\nWorld!", margin={'top': 1, 'left': 2}, padding={'right': 1})
        rendered = text_comp.render([], max_width=100)
        expected = "         \n  Hello  \n  World! "
        self.assertEqual(rendered, expected)

    def test_text_cannot_have_children(self):
        """Test that Text component cannot have children."""
        text_comp = Text("Hello")
        self.assertTrue(text_comp.leaf)
        self.assertEqual(text_comp.contents(), [])
        with self.assertRaises(ValueError):
            text_comp[Text("Child"),]
