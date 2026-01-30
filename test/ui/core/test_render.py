import time
import unittest

from ask.ui.core.components import Box, Text
from ask.ui.core.layout import layout
from ask.ui.core.render import render
from ask.ui.core.styles import Axis
from ask.ui.core.tree import ElementTree, mount
from test.ui.core.helpers import WideTree, DeepTree

class TestRender(unittest.TestCase):
    def test_empty_box(self):
        """Test empty box."""
        box = Box()[
            Box(),
            Text("Hello"),
        ]
        tree = ElementTree(box)
        mount(tree, box)
        layout(tree, box, 100)
        result = render(tree, box)
        self.assertEqual(result, "Hello")

    def test_width_types(self):
        """Test components with different width value types."""
        test_cases: list[tuple[str, int | None, list]] = [
            ("fixed width", 20, [('Left', 8, 8), ('Right', 8, 8)]),
            ("fractional width", 20, [('Left', 0.3, 6), ('Right', 0.7, 14)]),
            ("auto width", None, [('Hello', None, 5), ('World', None, 5)]),
            ("mixed width types", 30, [('Fixed', 10, 10), ('Fraction', 0.625, 10), ('Auto', None, 4)]),
        ]

        for description, width, _children in test_cases:
            with self.subTest(description=description):
                box = Box(width=width, flex=Axis.HORIZONTAL)[(Text(text, width=width) for text, width, _ in _children)]
                tree = ElementTree(box)
                mount(tree, box)
                layout(tree, box, 100)
                result = render(tree, box)
                expected_box_width = width or sum(expected_width for _, _, expected_width in _children)
                expected_result = ''.join(f'{text:<{expected_width}}' for text, _, expected_width in _children).ljust(expected_box_width)
                self.assertEqual(result, expected_result)

    def test_width_constrained_by_max_width(self):
        """Test components are constrained by max_width parameter."""
        text = Text("Very long text that should be wrapped")
        tree = ElementTree(text)
        mount(tree, text)
        layout(tree, text, 10)
        result = render(tree, text)
        self.assertEqual(result, "Very long \ntext that \nshould be \nwrapped   ")

    def test_width_constrained_by_parent_width(self):
        """Test components are constrained by parent width."""
        box = Box()[Box(width=10)[Text("Very long text that should be wrapped")]]
        tree = ElementTree(box)
        mount(tree, box)
        layout(tree, box, 100)
        result = render(tree, box)
        self.assertEqual(result, "Very long \ntext that \nshould be \nwrapped   ")

    def test_mixed_flex_components(self):
        """Test nested boxes with different flex directions."""
        outer = Box(flex=Axis.HORIZONTAL)[
            Box(flex=Axis.VERTICAL)[Text("Top"), Text("Bottom")],
            Text("Side")
        ]
        tree = ElementTree(outer)
        mount(tree, outer)
        layout(tree, outer, 100)
        result = render(tree, outer)
        self.assertEqual(result, "Top   Side\nBottom    ")


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
                self.assertLess(elapsed, 0.01, f"Render for {widget.__name__} took {elapsed*1000:.2f}ms, expected <10ms")
