import time
import unittest

from ask.ui.core.components import Box, Text, Spacing, Side
from ask.ui.core.layout import layout
from ask.ui.core.render import render
from ask.ui.core.styles import Axis, Borders
from ask.ui.core.tree import ElementTree, mount
from test.ui.core.helpers import WideTree, DeepTree

def render_once(element: Box | Text, max_width: int = 100) -> str:
    tree = ElementTree(element)
    mount(tree, element)
    layout(tree, element, max_width)
    return render(tree, element)


class TestRender(unittest.TestCase):
    def test_empty_box(self):
        box = Box()[Box(), Text("Hello")]
        self.assertEqual(render_once(box), "Hello")

    def test_width_types(self):
        test_cases: list[tuple[str, int | None, list]] = [
            ("fixed width", 20, [('Left', 8, 8), ('Right', 8, 8)]),
            ("fractional width", 20, [('Left', 0.3, 6), ('Right', 0.7, 14)]),
            ("auto width", None, [('Hello', None, 5), ('World', None, 5)]),
            ("mixed width types", 30, [('Fixed', 10, 10), ('Fraction', 0.625, 10), ('Auto', None, 4)]),
        ]

        for description, width, _children in test_cases:
            with self.subTest(description=description):
                box = Box(width=width, flex=Axis.HORIZONTAL)[(Text(text, width=width) for text, width, _ in _children)]
                expected_box_width = width or sum(expected_width for _, _, expected_width in _children)
                expected_result = ''.join(f'{text:<{expected_width}}' for text, _, expected_width in _children).ljust(expected_box_width)
                self.assertEqual(render_once(box), expected_result)

    def test_layout_width_constraint(self):
        text = Text("Very long text that should be wrapped")
        self.assertEqual(render_once(text, max_width=10), "Very long \ntext that \nshould be \nwrapped   ")

    def test_parent_width_constraint(self):
        box = Box()[Box(width=10)[Text("Very long text that should be wrapped")]]
        self.assertEqual(render_once(box), "Very long \ntext that \nshould be \nwrapped   ")

    def test_mixed_flex_components(self):
        outer = Box(flex=Axis.HORIZONTAL)[Box(flex=Axis.VERTICAL)[Text("Top"), Text("Bottom")], Text("Side")]
        self.assertEqual(render_once(outer), "Top   Side\nBottom    ")


class TestRenderMargin(unittest.TestCase):
    def test_margin(self):
        test_cases: list[tuple[str, str, Spacing, str]] = [
            ("no margin", "Hello", 0, "Hello"),
            ("uniform margin", "Hello", 1, "       \n Hello \n       "),
            ("asymmetric margin", "Hi", {'top': 2, 'bottom': 0, 'left': 3, 'right': 1}, "      \n      \n   Hi "),
            ("multiline with margin", "Line1\nLine2", {'top': 1, 'bottom': 1, 'left': 2, 'right': 2}, "         \n  Line1  \n  Line2  \n         "),
        ]
        for description, text_content, margin, expected in test_cases:
            with self.subTest(description=description):
                text = Text(text_content, margin=margin)
                self.assertEqual(render_once(text), expected)


class TestRenderBorder(unittest.TestCase):
    def test_border(self):
        test_cases: list[tuple[str, str, tuple[Side, ...], int, str]] = [
            ("no border", "Hello", (), 0, "Hello"),
            ("full border", "Hi", ('top', 'bottom', 'left', 'right'), 0, "┌──┐\n│Hi│\n└──┘"),
            ("partial border", "Hi", ('top', 'left'), 0, "┌──\n│Hi"),
            ("border with margin", "Hi", ('top', 'bottom', 'left', 'right'), 1, "      \n ┌──┐ \n │Hi│ \n └──┘ \n      "),
        ]
        for description, text_content, border, margin, expected in test_cases:
            with self.subTest(description=description):
                text = Text(text_content, margin=margin, border=border, border_style=Borders.SINGLE)
                self.assertEqual(render_once(text), expected)


class TestRenderPerformance(unittest.TestCase):
    def test_render_performance(self):
        for widget in (WideTree, DeepTree):
            with self.subTest(widget=widget.__name__):
                root = Box()[widget()]
                tree = ElementTree(root)
                mount(tree, root)
                layout(tree, root, 200)

                start = time.perf_counter()
                render(tree, root)
                elapsed = time.perf_counter() - start
                self.assertLess(elapsed, 0.03, f"Render for {widget.__name__} took {elapsed*1000:.2f}ms, expected <30ms")
