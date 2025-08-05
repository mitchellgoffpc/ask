import unittest
from ask.ui.components import Text, Spacing


class TestText(unittest.TestCase):
    def test_text_creation(self):
        """Test Text component creation with various props."""
        # Basic creation
        text_comp = Text("Hello World")
        self.assertEqual(text_comp.props['text'], "Hello World")
        self.assertEqual(text_comp.props['margin'], 0)
        self.assertTrue(text_comp.leaf)

        # With integer margin
        text_comp = Text("Hello", margin=2)
        self.assertEqual(text_comp.props['text'], "Hello")
        self.assertEqual(text_comp.props['margin'], 2)

        # With dictionary margin
        margin: Spacing = {'top': 1, 'bottom': 2, 'left': 3, 'right': 4}
        text_comp = Text("Hello", margin=margin)
        self.assertEqual(text_comp.props['text'], "Hello")
        self.assertEqual(text_comp.props['margin'], margin)

    def test_text_rendering(self):
        """Test Text component rendering with various margin configurations."""
        # No margin
        text_comp = Text("Hello World")
        rendered = text_comp.render([], max_width=100)
        self.assertEqual(rendered, "Hello World")

        # Integer margin
        text_comp = Text("Hello", margin=1)
        rendered = text_comp.render([], max_width=100)
        expected = "       \n Hello \n       "
        self.assertEqual(rendered, expected)

        # Dictionary margin
        margin: Spacing = {'top': 1, 'bottom': 0, 'left': 2, 'right': 1}
        text_comp = Text("Hello", margin=margin)
        rendered = text_comp.render([], max_width=100)
        expected = "        \n  Hello "
        self.assertEqual(rendered, expected)

        # Partial margin dictionary
        margin = {'top': 1, 'left': 2}
        text_comp = Text("Hello", margin=margin)
        rendered = text_comp.render([], max_width=100)
        expected = "       \n  Hello"
        self.assertEqual(rendered, expected)

        # Zero margin
        text_comp = Text("Hello", margin=0)
        rendered = text_comp.render([], max_width=100)
        self.assertEqual(rendered, "Hello")

    def test_text_multiline(self):
        """Test Text component rendering with multiline text."""
        # Multiline without margin
        text_comp = Text("Line 1\nLine 2\nLine 3")
        rendered = text_comp.render([], max_width=100)
        self.assertEqual(rendered, "Line 1\nLine 2\nLine 3")

        # Multiline with margin
        text_comp = Text("Line 1\nLine 2", margin=1)
        rendered = text_comp.render([], max_width=100)
        expected = "        \n Line 1 \n Line 2 \n        "
        self.assertEqual(rendered, expected)

    def test_text_empty_string(self):
        """Test Text component with empty string."""
        text_comp = Text("")
        rendered = text_comp.render([], max_width=100)
        self.assertEqual(rendered, "")

    def test_text_special_characters(self):
        """Test Text component with special and unicode characters."""
        # Special characters
        text_comp = Text("Hello\tWorld\n\rTest")
        rendered = text_comp.render([], max_width=100)
        self.assertEqual(rendered, "Hello\tWorld\n\rTest      ")

        # Unicode characters
        text_comp = Text("Hello 🌍 World ñáéíóú")
        rendered = text_comp.render([], max_width=100)
        self.assertEqual(rendered, "Hello 🌍 World ñáéíóú")

    def test_text_is_leaf_component(self):
        """Test that Text component is a leaf."""
        text_comp = Text("Hello")
        self.assertTrue(text_comp.leaf)
        self.assertEqual(text_comp.contents(), [])

    def test_text_cannot_have_children(self):
        """Test that Text component cannot have children."""
        text_comp = Text("Hello")
        with self.assertRaises(ValueError):
            text_comp[Text("Child"),]
