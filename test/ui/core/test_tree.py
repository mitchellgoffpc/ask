import time
import unittest
from collections import deque
from dataclasses import dataclass
from typing import ClassVar, Iterator

from ask.ui.core.components import Component, Box, Text, Controller, Widget
from ask.ui.core.tree import ElementTree, mount, update
from test.ui.core.helpers import WideTree, DeepTree

def toposort(tree: ElementTree) -> Iterator[Component]:
    queue = deque([tree.root.uuid])
    while queue:
        uuid = queue.popleft()
        yield tree.nodes[uuid]
        queue.extend(child.uuid for child in tree.children.get(uuid, []) if child)


@dataclass
class ChildWidget(Widget):
    __controller__: ClassVar = lambda _: ChildController
    value: int

class ChildController(Controller[ChildWidget]):
    def contents(self) -> list[Component | None]:
        return [Text(f"Child value: {self.props.value}")]

@dataclass
class ParentWidget(Widget):
    __controller__: ClassVar = lambda _: ParentController

class ParentController(Controller[ParentWidget]):
    child_value: int | None = 0

    def contents(self) -> list[Component | None]:
        return [Box()[ChildWidget(self.child_value) if self.child_value is not None else None]]

class TestTree(unittest.TestCase):
    def test_widget_mount_and_update(self):
        parent = ParentWidget()
        tree = ElementTree(parent)
        mount(tree, parent)

        _, box, child, text = toposort(tree)
        assert isinstance(box, Box) and isinstance(child, ChildWidget) and isinstance(text, Text)
        self.assertEqual(tree.parents, {box.uuid: parent.uuid, child.uuid: box.uuid, text.uuid: child.uuid})
        self.assertEqual(tree.children, {parent.uuid: [box], box.uuid: [child], child.uuid: [text], text.uuid: []})
        self.assertEqual(text.text, "Child value: 0")

        parent.controller.child_value = 1
        update(tree, parent)

        _, box2, child2, text2 = toposort(tree)
        assert isinstance(text2, Text)
        self.assertNotEqual(box2.uuid, box.uuid)
        self.assertEqual(child2.uuid, child.uuid)
        self.assertNotEqual(text2.uuid, text.uuid)
        self.assertEqual(tree.parents, {box2.uuid: parent.uuid, child2.uuid: box2.uuid, text2.uuid: child2.uuid})
        self.assertEqual(tree.children, {parent.uuid: [box2], box2.uuid: [child2], child2.uuid: [text2], text2.uuid: []})
        self.assertEqual(text2.text, "Child value: 1")

        parent.controller.child_value = 1
        update(tree, parent)

        _, box3, child3, text3 = toposort(tree)
        self.assertNotEqual(box2.uuid, box3.uuid)
        self.assertEqual(child3.uuid, child2.uuid)
        self.assertEqual(text3.uuid, text2.uuid)
        self.assertEqual(tree.parents, {box3.uuid: parent.uuid, child3.uuid: box3.uuid, text3.uuid: child3.uuid})
        self.assertEqual(tree.children, {parent.uuid: [box3], box3.uuid: [child3], child3.uuid: [text3], text3.uuid: []})

        parent.controller.child_value = None
        update(tree, parent)

        _, box4 = toposort(tree)
        self.assertTrue(box3.uuid != box4.uuid)
        self.assertEqual(tree.parents, {box4.uuid: parent.uuid})
        self.assertEqual(tree.children, {parent.uuid: [box4], box4.uuid: [None]})


class TestUpdatePerformance(unittest.TestCase):
    def test_update_performance(self):
        for widget in (WideTree, DeepTree):
            with self.subTest(widget=widget.__name__):
                root = Box()[widget()]
                tree = ElementTree(root)
                mount(tree, root)

                start = time.perf_counter()
                update(tree, root)
                elapsed = time.perf_counter() - start
                self.assertLess(elapsed, 0.01, f"Update for {widget.__name__} tree took {elapsed*1000:.2f}ms, expected <10ms")
