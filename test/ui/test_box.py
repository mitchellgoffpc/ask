import unittest
from ask.ui.components import Box, Text


class TestBox(unittest.TestCase):
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
