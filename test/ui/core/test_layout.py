import unittest

from ask.ui.core.components import ElementTree, Box, Text
from ask.ui.core.render import layout, mount
from ask.ui.core.styles import Flex

class TestLayout(unittest.TestCase):
    def test_flex_layout(self):
        test_cases: list[tuple[str, tuple, tuple, list[tuple], list[tuple]]] = [
            # description, parent_spec, expected_parent_size, children, expected_layouts (x, y, width, height)
            ("fixed widths", (Flex.HORIZONTAL, None, None), (30, 1), [('A', 10, None), ('B', 20, None)], [(0, 0, 10, 1), (10, 0, 20, 1)]),
            ("flexible widths", (Flex.HORIZONTAL, None, None), (10, 1), [('Hello', None, None), ('World', None, None)], [(0, 0, 5, 1), (5, 0, 5, 1)]),
            ("fractional widths", (Flex.HORIZONTAL, None, None), (100, 1), [('X', 0.25, None), ('Y', 0.75, None)], [(0, 0, 25, 1), (25, 0, 75, 1)]),
            ("mixed widths", (Flex.HORIZONTAL, None, None), (60, 1),
                [('Fixed', 10, None), ('Flex-12345', None, None), ('Frac', 0.5, None)],
                [(0, 0, 10, 1), (10, 0, 10, 1), (20, 0, 40, 1)]),

            ("fixed heights", (Flex.HORIZONTAL, None, None), (2, 5), [('A', None, 3), ('B', None, 5)], [(0, 0, 1, 3), (1, 0, 1, 5)]),
            ("flexible heights", (Flex.HORIZONTAL, None, None), (3, 1), [('A', None, None), ('BB', None, None)], [(0, 0, 1, 1), (1, 0, 2, 1)]),
            ("fractional heights", (Flex.HORIZONTAL, None, None), (2, 75), [('X', None, 0.25), ('Y', None, 0.75)], [(0, 0, 1, 25), (1, 0, 1, 75)]),
            ("mixed heights", (Flex.HORIZONTAL, None, None), (13, 50),
                [('Fixed', None, 5), ('Flex', None, None), ('Frac', None, 0.5)],
                [(0, 0, 5, 5), (5, 0, 4, 1), (9, 0, 4, 50)]),

            ("text width constraint", (Flex.HORIZONTAL, None, None), (20, 2), [('This text is longer than twenty chars', 20, None)], [(0, 0, 20, 2)]),
            ("child text width constraint", (Flex.HORIZONTAL, 20, None), (20, 2), [('This text is longer than twenty chars', None, None)], [(0, 0, 20, 2)]),
            ("child box width constraint", (Flex.HORIZONTAL, 20, None), (20, 1), [('A', 10, None), ('B', 20, None)], [(0, 0, 10, 1), (10, 0, 10, 1)]),

            ("fixed widths", (Flex.VERTICAL, None, None), (20, 2), [('A', 10, None), ('B', 20, None)], [(0, 0, 10, 1), (0, 1, 20, 1)]),
            ("flexible widths", (Flex.VERTICAL, None, None), (5, 2), [('Hello', None, None), ('World', None, None)], [(0, 0, 5, 1), (0, 1, 5, 1)]),
            ("fractional widths", (Flex.VERTICAL, None, None), (75, 2), [('X', 0.25, None), ('Y', 0.75, None)], [(0, 0, 25, 1), (0, 1, 75, 1)]),

            ("fixed heights", (Flex.VERTICAL, None, None), (1, 8), [('A', None, 3), ('B', None, 5)], [(0, 0, 1, 3), (0, 3, 1, 5)]),
            ("flexible heights", (Flex.VERTICAL, None, None), (2, 2), [('A', None, None), ('BB', None, None)], [(0, 0, 1, 1), (0, 1, 2, 1)]),
            ("fractional heights", (Flex.VERTICAL, None, None), (1, 100), [('X', None, 0.25), ('Y', None, 0.75)], [(0, 0, 1, 25), (0, 25, 1, 75)]),
        ]

        for description, (flex, width, height), (expected_width, expected_height), children, expected_layouts in test_cases:
            with self.subTest(flex=flex, description=description):
                tree = ElementTree()
                texts = [Text(text, width=width, height=height) for text, width, height in children]
                box = Box(flex=flex, width=width, height=height)[texts]
                mount(tree, box)
                layout(tree, box, 100, 100)

                self.assertEqual(tree.widths[box.uuid], expected_width)
                self.assertEqual(tree.heights[box.uuid], expected_height)
                for child, (x, y, width, height) in zip(texts, expected_layouts, strict=True):
                    self.assertEqual(tree.widths[child.uuid], width)
                    self.assertEqual(tree.heights[child.uuid], height)
                    self.assertEqual(tree.offsets[child.uuid].x, x)
                    self.assertEqual(tree.offsets[child.uuid].y, y)

    def test_nested_flex_layout(self):
        test_cases = [
            # description, outer_box_spec, inner_box_spec, text, expected_outer_size, expected_text_size
            ("fixed width", (None, None), (None, None), ('A', 10, None), (10, 1), (10, 1)),
            ("fixed height", (None, None), (None, None), ('A', None, 3), (1, 3), (1, 3)),
            ("fractional width", (None, None), (None, None), ('Hello', 1.0, None), (100, 1), (100, 1)),
            ("fractional height", (None, None), (None, None), ('X', None, 0.5), (1, 50), (1, 50)),
            ("nested fractional width", (None, None), (0.5, None), ('Hello', 0.5, None), (50, 1), (25, 1)),
            ("nested fractional height", (None, None), (None, 0.5), ('X', None, 0.5), (1, 50), (1, 25)),
            ("child width constraint", (20, None), (None, None), ('Wide', 30, None), (20, 1), (20, 1)),
            ("child height constraint", (None, 3), (None, None), ('Tall', None, 5), (4, 3), (4, 3)),
        ]

        for description, (outer_w, outer_h), (inner_w, inner_h), (text, w, h), (exp_outer_w, exp_outer_h), (exp_text_w, exp_text_h) in test_cases:
            with self.subTest(description=description):
                tree = ElementTree()
                text_elem = Text(text, width=w, height=h)
                outer_box = Box(width=outer_w, height=outer_h)[Box(width=inner_w, height=inner_h)[text_elem]]
                mount(tree, outer_box)
                layout(tree, outer_box, 100, 100)

                self.assertEqual(tree.widths[outer_box.uuid], exp_outer_w)
                self.assertEqual(tree.heights[outer_box.uuid], exp_outer_h)
                self.assertEqual(tree.widths[text_elem.uuid], exp_text_w)
                self.assertEqual(tree.heights[text_elem.uuid], exp_text_h)

    def test_chrome_layout(self):
        def make_chrome(m: int, b: int, p: int) -> dict:
            return {'margin': m, 'border': ('top', 'bottom', 'left', 'right') if b else (), 'padding': p}

        test_cases: list[tuple[str, Flex, tuple, tuple, list[tuple], list[tuple]]] = [
            # description, flex, parent_chrome, expected_parent_size, children [(text, width, height, chrome)], expected_layouts (x, y, width, height)
            ("parent chrome h", Flex.HORIZONTAL, (2, 1, 3), (100, 13), [('A', 1.0, None, (0, 0, 0))], [(6, 6, 88, 1)]),
            ("parent chrome v", Flex.VERTICAL, (2, 1, 3), (13, 100), [('A', None, 1.0, (0, 0, 0))], [(6, 6, 1, 88)]),
            ("child chrome h, fixed width", Flex.HORIZONTAL, (0, 0, 0), (40, 13),
                [('A', 20, None, (2, 1, 3)), ('B', 20, None, (0, 0, 0))],
                [(0, 0, 20, 13), (20, 0, 20, 1)]),
            ("child chrome v, fixed height", Flex.VERTICAL, (0, 0, 0), (13, 40),
                [('A', None, 20, (2, 1, 3)), ('B', None, 20, (0, 0, 0))],
                [(0, 0, 13, 20), (0, 20, 1, 20)]),
            ("child chrome h, flexible width", Flex.HORIZONTAL, (0, 0, 0), (14, 13),
                [('A', None, None, (2, 1, 3)), ('B', None, None, (0, 0, 0))],
                [(0, 0, 13, 13), (13, 0, 1, 1)]),
            ("child chrome v, fixed height", Flex.VERTICAL, (0, 0, 0), (13, 14),
                [('A', None, None, (2, 1, 3)), ('B', None, None, (0, 0, 0))],
                [(0, 0, 13, 13), (0, 13, 1, 1)]),
        ]

        for description, flex, chrome, (expected_w, expected_h), children, expected_layouts in test_cases:
            with self.subTest(flex=flex, description=description):
                tree = ElementTree()
                texts = [Text(text, width=width, height=height, **make_chrome(*chrome)) for text, width, height, chrome in children]
                box = Box(flex=flex, **make_chrome(*chrome))[texts]
                mount(tree, box)
                layout(tree, box, 100, 100)

                self.assertEqual(tree.widths[box.uuid], expected_w)
                self.assertEqual(tree.heights[box.uuid], expected_h)
                for child, (x, y, width, height) in zip(texts, expected_layouts, strict=True):
                    self.assertEqual(tree.offsets[child.uuid].x, x)
                    self.assertEqual(tree.offsets[child.uuid].y, y)
                    self.assertEqual(tree.widths[child.uuid], width)
                    self.assertEqual(tree.heights[child.uuid], height)
