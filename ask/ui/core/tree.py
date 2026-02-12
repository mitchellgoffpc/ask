from dataclasses import asdict, is_dataclass
from itertools import zip_longest
from typing import Any, NamedTuple
from uuid import UUID

from ask.ui.core.components import Component, Element, Text, Widget


class Offset(NamedTuple):
    x: int
    y: int

class ElementTree:
    def __init__(self, root: Component) -> None:
        self.root = root
        self.nodes: dict[UUID, Component] = {}
        self.parents: dict[UUID, UUID] = {}
        self.children: dict[UUID, list[Component | None]] = {}
        self.collapsed_children: dict[UUID, list[Element]] = {}
        self.offsets: dict[UUID, Offset] = {}
        self.widths: dict[UUID, int] = {}
        self.heights: dict[UUID, int] = {}
        self.dirty: set[UUID] = set()

    def __str__(self) -> str:
        return self.format(self.root.uuid)

    def format(self, uuid: UUID, level: int = 0, verbose: bool = False) -> str:
        prefix = '  ' * (max(0, level - 1)) + ('└─' if level > 0 else '')
        match self.nodes[uuid]:
            case Text(text=text): attrs = {'text': text}
            case Widget() as widget if is_dataclass(widget): attrs = asdict(widget)
            case _: attrs = {}
        uuid_str = f"{str(uuid).split('-')[0]} → " if verbose else ''
        attrs_str = '('  + ', '.join(f'{k}={v!r}' for k, v in attrs.items()) + ')'
        result = f"{prefix}{uuid_str}{self.nodes[uuid].__class__.__name__}{attrs_str if attrs else ''}\n"
        for child in self.children.get(uuid, []):
            if child:
                result += self.format(child.uuid, level + 1, verbose=verbose)
        return result


# Utility functions

def depth(tree: ElementTree, node: Component) -> int:
    depth = 0
    while node is not tree.root:
        node = tree.nodes[tree.parents[node.uuid]]
        depth += 1
    return depth

# Propogate input to a component and its subtree
def propogate(tree: ElementTree, node: Component, value: Any, event_type: str) -> None:
    if isinstance(node, Widget):
        getattr(node.controller, f'handle_{event_type}')(value)
    for child in tree.children.get(node.uuid, []):
        if child:
            propogate(tree, child, value, event_type)

# Add a component and all its children to the tree
def mount(tree: ElementTree, component: Component) -> None:
    if isinstance(component, Widget):
        component.controller = component.Controller(component)
        component.controller.handle_mount(tree)
    tree.nodes[component.uuid] = component
    contents = component.contents()
    tree.children[component.uuid] = contents
    for child in contents:
        if child:
            mount(tree, child)
            tree.parents[child.uuid] = component.uuid

# Remove a component and all its children from the tree
def unmount(tree: ElementTree, component: Component) -> None:
    for child in tree.children[component.uuid]:
        if child:
            unmount(tree, child)
    del tree.nodes[component.uuid], tree.children[component.uuid], tree.parents[component.uuid]
    tree.collapsed_children.pop(component.uuid, None)
    tree.offsets.pop(component.uuid, None)
    tree.widths.pop(component.uuid, None)
    tree.heights.pop(component.uuid, None)
    if isinstance(component, Widget):
        component.controller.handle_unmount()
        component.controller = None

# Update a component's subtree
def update(tree: ElementTree, component: Component) -> None:
    uuid = component.uuid
    new_contents = component.contents()
    old_contents = tree.children[uuid]

    for i, (old_child, new_child) in enumerate(zip_longest(old_contents, new_contents, fillvalue=None)):
        if not old_child and not new_child:
            continue
        elif new_child and not old_child:
            # New child added
            if i >= len(tree.children[uuid]):
                tree.children[uuid].append(new_child)
            else:
                tree.children[uuid][i] = new_child
            mount(tree, new_child)
            tree.parents[new_child.uuid] = uuid
        elif old_child and not new_child:
            # Child removed
            unmount(tree, old_child)
            tree.children[uuid][i] = None
        elif old_child and new_child and type(old_child) is not type(new_child):
            # Class changed, replace the child
            assert tree.parents[old_child.uuid] == uuid
            unmount(tree, old_child)
            mount(tree, new_child)
            tree.parents[new_child.uuid] = uuid
            tree.children[uuid][i] = new_child
        elif old_child and new_child and type(old_child) is type(new_child):
            # Class is the same, update recursively
            if isinstance(old_child, Widget) and isinstance(new_child, Widget):
                if old_child == new_child:
                    continue
                new_child.controller = old_child.controller
                new_child.controller(new_child)
            assert tree.parents[old_child.uuid] == uuid
            del tree.nodes[old_child.uuid]
            tree.nodes[new_child.uuid] = new_child
            tree.parents[new_child.uuid] = tree.parents.pop(old_child.uuid)
            tree.children[new_child.uuid] = tree.children.pop(old_child.uuid)
            tree.collapsed_children.pop(old_child.uuid, None)
            tree.offsets.pop(old_child.uuid, None)
            tree.widths.pop(old_child.uuid, None)
            tree.heights.pop(old_child.uuid, None)
            for child in tree.children.get(new_child.uuid, []):
                if child:
                    tree.parents[child.uuid] = new_child.uuid
            tree.children[uuid][i] = new_child
            update(tree, new_child)
