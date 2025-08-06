import unittest
from ask.ui.components import Text


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
