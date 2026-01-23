import asyncio
import fcntl
import os
import select
import shutil
import sys
import termios
import tty
from contextlib import contextmanager
from itertools import zip_longest
from typing import Any, Iterator
from uuid import UUID

from ask.ui.core.components import ElementTree, Component, Element, Box, Widget, get_rendered_width
from ask.ui.core.cursor import hide_cursor, show_cursor, erase_line, cursor_up
from ask.ui.core.styles import Flex, ansi_len

# Context manager to set O_NONBLOCK on a file descriptor
@contextmanager
def nonblocking(fd: int) -> Iterator[None]:
    original_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    try:
        fcntl.fcntl(fd, fcntl.F_SETFL, original_fl | os.O_NONBLOCK)
        yield
    finally:
        fcntl.fcntl(fd, fcntl.F_SETFL, original_fl)

# Utility function to print the component tree
def print_node(tree: ElementTree, uuid: UUID, level: int = 0) -> None:
    component = tree.nodes[uuid]
    print('  ' * level + f'└─ {component.__class__.__name__}')
    for child in tree.children.get(uuid, []):
        if child:  # Skip None values
            print_node(tree, child.uuid, level + 1)

# Add a component and all its children to the tree
def mount(tree: ElementTree, component: Component) -> None:
    if isinstance(component, Widget):
        component.controller = component.__controller__()(component)
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
                new_child.controller = old_child.controller
                new_child.controller(new_child)
            assert tree.parents[old_child.uuid] == uuid
            del tree.nodes[old_child.uuid]
            tree.nodes[new_child.uuid] = new_child
            tree.parents[new_child.uuid] = tree.parents.pop(old_child.uuid)
            tree.children[new_child.uuid] = tree.children.pop(old_child.uuid)
            for child in tree.children.get(new_child.uuid, []):
                if child:
                    tree.parents[child.uuid] = new_child.uuid
            tree.children[uuid][i] = new_child
            update(tree, new_child)


# Render a component and its subtree to a string
def collapse(tree: ElementTree, component: Component | None) -> list[Element]:
    match component:
        case None: return []
        case Widget(): return [x for child in tree.children[component.uuid] for x in collapse(tree, child)]
        case Element(): return [component]
        case _: raise ValueError(f"Unknown component type: {type(component)}")

def render(tree: ElementTree, element: Element, width: int) -> str:
    remaining_width = element.get_content_width(width)
    flex = element.flex if isinstance(element, Box) else Flex.VERTICAL
    collapsed = [x for child in tree.children[element.uuid] for x in collapse(tree, child)]
    renders = {}
    for i, c in enumerate(collapsed):
        if isinstance(c.width, int) and remaining_width > 0:
            renders[i] = render(tree, c, c.width)
            remaining_width -= c.rendered_width if flex is Flex.HORIZONTAL else 0
    for i, c in enumerate(collapsed):
        if c.width is None and remaining_width > 0:
            renders[i] = render(tree, c, remaining_width)
            remaining_width -= c.rendered_width if flex is Flex.HORIZONTAL else 0

    if flex is Flex.HORIZONTAL:
        scale = remaining_width / max(1, sum(c.width for c in collapsed if isinstance(c.width, float)))
    elif flex is Flex.VERTICAL:
        scale = float(remaining_width)
    for i, c in enumerate(collapsed):
        if c and isinstance(c.width, float) and remaining_width > 0:
            renders[i] = render(tree, c, min(remaining_width, int(c.width * scale)))
            remaining_width -= c.rendered_width

    contents = [c for _, c in sorted(renders.items())]
    rendered = element.render(contents, width)
    element.rendered_width = get_rendered_width(rendered)
    return rendered

# Get the depth of a node
def depth(tree: ElementTree, node: Component, root: Component) -> int:
    depth = 0
    while node is not root:
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


# Main render loop

async def render_root(_root: Component) -> None:
    hide_cursor()

    tree = ElementTree()
    root = _root if isinstance(_root, Element) else Box()[_root]  # Root component needs to be an element
    mount(tree, root)
    initial_render = render(tree, root, shutil.get_terminal_size().columns)
    previous_render_lines = initial_render.split('\n')
    print('\n\r'.join(previous_render_lines))

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ready, _, _ = select.select([sys.stdin], [], [], 0.05)
            if ready:
                with nonblocking(fd):
                    sequence = ''
                    while (ch := sys.stdin.read(1)):
                        sequence += ch
                propogate(tree, root, sequence, 'input')

            # Check for dirty components
            if not tree.dirty:
                await asyncio.sleep(0.01)
                continue
            for uuid in sorted(tree.dirty, key=lambda uuid: depth(tree, tree.nodes[uuid], root)):  # start at the top and work downwards
                if uuid in tree.nodes:
                    update(tree, tree.nodes[uuid])
            tree.dirty.clear()

            # Re-render the tree
            terminal_size = shutil.get_terminal_size()
            new_render_lines = render(tree, root, terminal_size.columns).split('\n')

            # Check if we need to clear screen due to large difference in output size
            if len(previous_render_lines) - len(new_render_lines) > min(terminal_size.lines / 2, terminal_size.lines - 20):
                sys.stdout.write('\033c')
                previous_render_lines = []

            # Pad new render to match the number of previous lines
            max_lines = max(len(previous_render_lines), len(new_render_lines))
            new_render_lines.extend([''] * (max_lines - len(new_render_lines)))

            # If there are unchanged leading lines, move cursor to the first changed line
            line_diffs = zip_longest(previous_render_lines, new_render_lines, fillvalue='')
            first_diff_idx = next((i for i, (prev, new) in enumerate(line_diffs) if prev != new), None)
            if first_diff_idx is None:
                await asyncio.sleep(0.01)
                continue

            output = cursor_up(len(previous_render_lines) - first_diff_idx)
            for prev_line, new_line in zip_longest(previous_render_lines[first_diff_idx:], new_render_lines[first_diff_idx:], fillvalue=''):
                sys.stdout.write('\r')
                if ansi_len(new_line) < ansi_len(prev_line):
                    output += erase_line
                output += new_line + '\n\r'

            sys.stdout.write(output)
            sys.stdout.flush()
            previous_render_lines = new_render_lines
            await asyncio.sleep(0.01)

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        show_cursor()
        sys.stdout.write('\n')
        sys.stdout.flush()
