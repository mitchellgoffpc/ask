import unittest

from ask.ui.core.components import ElementTree, Box, Text
from ask.ui.core.render import render, mount
from ask.ui.core.styles import Flex

class TestRender(unittest.TestCase):
    def setUp(self):
        self.tree = ElementTree()

    def test_empty_box(self):
        """Test empty box."""
        box = Box()[
            Box(),
            Text("Hello"),
        ]
        mount(self.tree, box)
        result = render(self.tree, box, 100)
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
                box = Box(width=width, flex=Flex.HORIZONTAL)[
                    *(Text(text, width=width) for text, width, _ in _children)
                ]
                mount(self.tree, box)
                result = render(self.tree, box, width or 100)

                expected_box_width = width or sum(expected_width for _, _, expected_width in _children)
                expected_result = ''.join(f'{text:<{expected_width}}' for text, _, expected_width in _children).ljust(expected_box_width)
                self.assertEqual(result, expected_result)

    def test_width_constrained_by_max_width(self):
        """Test components are constrained by max_width parameter."""
        text = Text("Very long text that should be wrapped")
        mount(self.tree, text)
        result = render(self.tree, text, 10)
        self.assertEqual(result, "Very long \ntext that \nshould be \nwrapped   ")

    def test_width_constrained_by_parent_width(self):
        """Test components are constrained by parent width."""
        box = Box()[
            Box(width=10)[
                Text("Very long text that should be wrapped")
            ]
        ]
        mount(self.tree, box)
        result = render(self.tree, box, 100)
        self.assertEqual(result, "Very long \ntext that \nshould be \nwrapped   ")

    def test_mixed_flex_components(self):
        """Test nested boxes with different flex directions."""
        outer = Box(flex=Flex.HORIZONTAL)[
            Box(flex=Flex.VERTICAL)[
                Text("Top"),
                Text("Bottom")
            ],
            Text("Side")
        ]
        mount(self.tree, outer)
        result = render(self.tree, outer, 100)
        self.assertEqual(result, "Top   Side\nBottom    ")
