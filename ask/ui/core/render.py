import asyncio
import fcntl
import os
import select
import shutil
import sys
import termios
import tty
from contextlib import contextmanager
from itertools import chain, zip_longest
from typing import Any, Iterator
from uuid import UUID

from ask.ui.core.components import ElementTree, Offset, Component, Element, Box, Text, Widget, ansi_len, apply_boxing, apply_sizing
from ask.ui.core.cursor import hide_cursor, show_cursor, erase_line, cursor_up
from ask.ui.core.styles import Axis

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


# Update functions - mount, unmount, update

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


# Layout functions - compute sizes and offsets before rendering

def layout(tree: ElementTree, element: Element, available_width: int | None = None, available_height: int | None = None) -> None:
    collapse_tree(tree, element)
    compute_lengths(tree, element, Axis.HORIZONTAL, available_width)
    compute_lengths(tree, element, Axis.VERTICAL, available_height)
    compute_offsets(tree, element)

def collapse_tree(tree: ElementTree, element: Element) -> None:
    tree.collapsed_children[element.uuid] = list(chain.from_iterable(collapse_children(tree, child) for child in tree.children[element.uuid]))
    for child in tree.collapsed_children[element.uuid]:
        collapse_tree(tree, child)

def collapse_children(tree: ElementTree, component: Component | None) -> list[Element]:
    match component:
        case None: return []
        case Widget(): return list(chain.from_iterable(collapse_children(tree, child) for child in tree.children[component.uuid]))
        case Element(): return [component]
        case _: raise ValueError(f"Unknown component type: {type(component)}")

def compute_lengths(tree: ElementTree, element: Element, axis: Axis, available_length: int | None = None) -> None:
    flex = element.flex if isinstance(element, Box) else Axis.VERTICAL
    collapsed = tree.collapsed_children[element.uuid]
    child_lengths = [child.length(axis) for child in collapsed]
    computed_lengths = tree.widths if axis is Axis.HORIZONTAL else tree.heights

    if isinstance((element_length := element.length(axis)), int):
        available_length = min(available_length, element_length) if available_length is not None else element_length
    content_length = element.get_content_length(axis, available_length) if available_length else None
    remaining_length = content_length

    # First: fixed-length children (int)
    for child, child_length in zip(collapsed, child_lengths, strict=True):
        if isinstance(child_length, int):
            compute_lengths(tree, child, axis, min(remaining_length, child_length) if remaining_length is not None else child_length)
            if flex is axis and remaining_length is not None:
                remaining_length = max(0, remaining_length - computed_lengths[child.uuid])

    # Second: flexible-length children (None)
    for child, child_length in zip(collapsed, child_lengths, strict=True):
        if child_length is None or (isinstance(child_length, float) and remaining_length is None):
            compute_lengths(tree, child, axis, remaining_length)
            if flex is axis and remaining_length is not None:
                remaining_length = max(0, remaining_length - computed_lengths[child.uuid])

    # Third: fractional-length children (float)
    if remaining_length is not None:
        total_fraction = sum(x for x in child_lengths if isinstance(x, float))
        scale = remaining_length / max(1, total_fraction) if flex is axis else float(remaining_length)
        for child, child_length in zip(collapsed, child_lengths, strict=True):
            if isinstance(child_length, float):
                scaled_length = min(remaining_length, int(child_length * scale))
                compute_lengths(tree, child, axis, scaled_length)
                remaining_length = max(0, remaining_length - computed_lengths[child.uuid])

    # Compute this element's length based on its length specification
    if isinstance(element_length, int):
        final_length = element_length
    elif isinstance(element_length, float):
        final_length = available_length or 0
    else:  # None - flexible, size to content
        if isinstance(element, Text):
            if axis is Axis.HORIZONTAL:
                wrapped = element.wrap(content_length) if content_length else element.text.replace('\t', ' ' * 8)
                inner_length = max((ansi_len(line) for line in wrapped.split('\n')), default=0)
            else:  # VERTICAL - heights depend on widths for text wrapping
                content_width = element.get_content_width(tree.widths[element.uuid])
                wrapped = element.wrap(content_width)
                inner_length = wrapped.count('\n') + 1 if wrapped else 0
        elif flex is axis:
            inner_length = sum((computed_lengths[c.uuid] for c in collapsed), start=0)
        else:
            inner_length = max((computed_lengths[c.uuid] for c in collapsed), default=0)
        final_length = inner_length + element.chrome(axis)

    computed_lengths[element.uuid] = min(available_length, final_length) if available_length is not None else final_length

def compute_offsets(tree: ElementTree, element: Element) -> None:
    flex = element.flex if isinstance(element, Box) else Axis.VERTICAL
    x_offset = element.margin['left'] + element.border['left'] + element.padding['left']
    y_offset = element.margin['top'] + element.border['top'] + element.padding['top']

    for child in tree.collapsed_children[element.uuid]:
        tree.offsets[child.uuid] = Offset(x=x_offset, y=y_offset)
        if flex is Axis.HORIZONTAL:
            x_offset += tree.widths[child.uuid]
        else:
            y_offset += tree.heights[child.uuid]
        compute_offsets(tree, child)


# Rendering

def render(tree: ElementTree, element: Element) -> str:
    width = tree.widths[element.uuid]
    height = tree.heights[element.uuid]
    content_width = element.get_content_width(width)
    content_height = element.get_content_height(height)

    match element:
        case Text():
            content = element.wrap(content_width)
        case Box():
            collapsed = tree.collapsed_children[element.uuid]
            contents = [render(tree, child) for child in collapsed]
            if element.flex is Axis.VERTICAL:
                content = '\n'.join(x for x in contents if x)
            else:
                max_child_height = max((tree.heights[child.uuid] for child in collapsed), default=0)
                contents = [apply_sizing(child_content, tree.widths[child.uuid], max_child_height)
                            for child_content, child in zip(contents, collapsed, strict=True)]
                lines = [child.split('\n') for child in contents]
                content = '\n'.join(''.join(columns) for columns in zip(*lines, strict=True))
        case _:
            raise ValueError(f"Unknown element type: {type(element)}")

    return apply_boxing(content, content_width, content_height, element)


# Main render loop

async def render_root(_root: Component) -> None:
    hide_cursor()

    tree = ElementTree()
    root = _root if isinstance(_root, Element) else Box()[_root]  # Root component needs to be an element
    mount(tree, root)
    terminal_width = shutil.get_terminal_size().columns
    layout(tree, root, terminal_width)
    initial_render = render(tree, root)
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
            layout(tree, root, terminal_size.columns)
            new_render_lines = render(tree, root).split('\n')

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
