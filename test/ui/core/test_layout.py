import unittest

from ask.ui.core.components import ElementTree, Box, Text
from ask.ui.core.render import layout, mount
from ask.ui.core.styles import Flex

class TestLayout(unittest.TestCase):
    def test_flex_layout(self):
        test_cases = [
            # flex, description, parent_size, expected_parent_size, children, expected_layouts (x, y, width, height)
            (Flex.HORIZONTAL, "fixed widths", (None, None), (30, 1), [('A', 10, None), ('B', 20, None)], [(0, 0, 10, 1), (10, 0, 20, 1)]),
            (Flex.HORIZONTAL, "flexible widths", (None, None), (10, 1), [('Hello', None, None), ('World', None, None)], [(0, 0, 5, 1), (5, 0, 5, 1)]),
            (Flex.HORIZONTAL, "fractional widths", (None, None), (100, 1), [('X', 0.25, None), ('Y', 0.75, None)], [(0, 0, 25, 1), (25, 0, 75, 1)]),
            (Flex.HORIZONTAL, "mixed widths", (None, None), (60, 1),
                [('Fixed', 10, None), ('Flex-12345', None, None), ('Frac', 0.5, None)],
                [(0, 0, 10, 1), (10, 0, 10, 1), (20, 0, 40, 1)]),

            (Flex.VERTICAL, "fixed widths", (None, None), (20, 2), [('A', 10, None), ('B', 20, None)], [(0, 0, 10, 1), (0, 1, 20, 1)]),
            (Flex.VERTICAL, "flexible widths", (None, None), (5, 2), [('Hello', None, None), ('World', None, None)], [(0, 0, 5, 1), (0, 1, 5, 1)]),
            (Flex.VERTICAL, "fractional widths", (None, None), (75, 2), [('X', 0.25, None), ('Y', 0.75, None)], [(0, 0, 25, 1), (0, 1, 75, 1)]),

            (Flex.HORIZONTAL, "text width constraint", (None, None), (20, 2), [('This text is longer than twenty chars', 20, None)], [(0, 0, 20, 2)]),
            (Flex.HORIZONTAL, "child text width constraint", (20, None), (20, 2), [('This text is longer than twenty chars', None, None)], [(0, 0, 20, 2)]),
            (Flex.HORIZONTAL, "child box width constraint", (20, None), (20, 1), [('A', 10, None), ('B', 20, None)], [(0, 0, 10, 1), (10, 0, 10, 1)]),

            (Flex.HORIZONTAL, "fixed heights", (None, None), (2, 5), [('A', None, 3), ('B', None, 5)], [(0, 0, 1, 3), (1, 0, 1, 5)]),
            (Flex.HORIZONTAL, "flexible heights", (None, None), (3, 1), [('A', None, None), ('BB', None, None)], [(0, 0, 1, 1), (1, 0, 2, 1)]),
            (Flex.HORIZONTAL, "fractional heights", (None, None), (2, 75), [('X', None, 0.25), ('Y', None, 0.75)], [(0, 0, 1, 25), (1, 0, 1, 75)]),
            (Flex.HORIZONTAL, "mixed heights", (None, None), (13, 50),
                [('Fixed', None, 5), ('Flex', None, None), ('Frac', None, 0.5)],
                [(0, 0, 5, 5), (5, 0, 4, 1), (9, 0, 4, 50)]),

            (Flex.VERTICAL, "fixed heights", (None, None), (1, 8), [('A', None, 3), ('B', None, 5)], [(0, 0, 1, 3), (0, 3, 1, 5)]),
            (Flex.VERTICAL, "flexible heights", (None, None), (2, 2), [('A', None, None), ('BB', None, None)], [(0, 0, 1, 1), (0, 1, 2, 1)]),
            (Flex.VERTICAL, "fractional heights", (None, None), (1, 100), [('X', None, 0.25), ('Y', None, 0.75)], [(0, 0, 1, 25), (0, 25, 1, 75)]),
        ]

        for flex, description, (width, height), (expected_width, expected_height), children, expected_layouts in test_cases:
            with self.subTest(flex=flex, description=description):
                tree = ElementTree()
                box = Box(flex=flex, width=width, height=height)[(Text(text, width=width, height=height) for text, width, height in children)]
                mount(tree, box)
                layout(tree, box, 100, 100)

                self.assertEqual(tree.sizes[box.uuid].width, expected_width)
                self.assertEqual(tree.sizes[box.uuid].height, expected_height)
                for child, (x, y, width, height) in zip(box.children, expected_layouts, strict=True):
                    self.assertEqual(tree.sizes[child.uuid].width, width)
                    self.assertEqual(tree.sizes[child.uuid].height, height)
                    self.assertEqual(tree.offsets[child.uuid].x, x)
                    self.assertEqual(tree.offsets[child.uuid].y, y)
