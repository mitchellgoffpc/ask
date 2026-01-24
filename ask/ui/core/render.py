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

from ask.ui.core.components import ElementTree, Component, Element, Box, Text, Widget, Offset
from ask.ui.core.cursor import hide_cursor, show_cursor, erase_line, cursor_up
from ask.ui.core.styles import Flex, ansi_len, wrap_lines

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


# Layout functions - compute sizes and offsets before rendering

def layout(tree: ElementTree, element: Element, available_width: int, available_height: int | None = None) -> None:
    """Main layout function that computes sizes and offsets for all elements."""
    compute_widths(tree, element, available_width)
    compute_heights(tree, element, available_height)
    compute_offsets(tree, element)


def compute_widths(tree: ElementTree, element: Element, available_width: int) -> None:
    """First pass: compute widths for element and all descendants.

    Order of operations: fixed-width (int) -> flexible-width (None) -> fractional-width (float)
    """
    flex = element.flex if isinstance(element, Box) else Flex.VERTICAL
    collapsed = [x for child in tree.children[element.uuid] for x in collapse(tree, child)]
    if isinstance(element.width, int):
        available_width = min(available_width, element.width)
    content_width = element.get_content_width(available_width)
    remaining_width = content_width

    # First: fixed-width children (int)
    for child in collapsed:
        if isinstance(child.width, int):
            compute_widths(tree, child, min(child.width, remaining_width))
            if flex is Flex.HORIZONTAL:
                remaining_width = max(0, remaining_width - tree.widths[child.uuid])

    # Second: flexible-width children (None)
    for child in collapsed:
        if child.width is None:
            compute_widths(tree, child, remaining_width)
            if flex is Flex.HORIZONTAL:
                remaining_width = max(0, remaining_width - tree.widths[child.uuid])

    # Third: fractional-width children (float)
    total_fraction = sum(c.width for c in collapsed if isinstance(c.width, float))
    if flex is Flex.HORIZONTAL:
        scale = remaining_width / max(1, total_fraction)
    else:
        scale = float(remaining_width)
    for child in collapsed:
        if isinstance(child.width, float):
            scaled_width = min(remaining_width, int(child.width * scale))
            compute_widths(tree, child, scaled_width)
            remaining_width = max(0, remaining_width - tree.widths[child.uuid])

    # Compute this element's width based on its width specification
    if isinstance(element.width, int):
        final_width = element.width
    elif isinstance(element.width, float):
        final_width = available_width
    else:  # None - flexible, size to content
        if isinstance(element, Text):
            wrapped = wrap_lines(element.text.replace('\t', ' ' * 8), content_width)
            inner_width = max((ansi_len(line) for line in wrapped.split('\n')), default=0)
        elif flex is Flex.HORIZONTAL:
            inner_width = sum((tree.widths[c.uuid] for c in collapsed), start=0)
        else:
            inner_width = max((tree.widths[c.uuid] for c in collapsed), default=0)
        final_width = inner_width + element.get_horizontal_chrome()

    tree.widths[element.uuid] = min(available_width, final_width)


def compute_heights(tree: ElementTree, element: Element, available_height: int | None = None) -> None:
    """Second pass: compute heights for element and all descendants.

    Heights depend on widths (e.g., text wrapping), so this runs after compute_widths.
    Order of operations: fixed-height (int) -> flexible-height (None) -> fractional-height (float)
    """
    flex = element.flex if isinstance(element, Box) else Flex.VERTICAL
    collapsed = [x for child in tree.children[element.uuid] for x in collapse(tree, child)]
    if isinstance(element.height, int):
        available_height = min(available_height, element.height) if available_height is not None else element.height
    content_height = element.get_content_height(available_height) if available_height else None
    remaining_height = content_height

    # First: fixed-height children (int) and flexible-height children (None)
    # These are processed together since flexible heights are intrinsic (don't need remaining space)
    for child in collapsed:
        if isinstance(child.height, int):
            compute_heights(tree, child, min(remaining_height, child.height) if remaining_height is not None else child.height)
            if flex is Flex.VERTICAL and remaining_height is not None:
                remaining_height = max(0, remaining_height - tree.heights[child.uuid])
        elif child.height is None:
            compute_heights(tree, child, remaining_height)
            if flex is Flex.VERTICAL and remaining_height is not None:
                remaining_height = max(0, remaining_height - tree.heights[child.uuid])

    # Second: fractional-height children (float)
    if remaining_height is not None:
        total_fraction = sum(c.height for c in collapsed if isinstance(c.height, float))
        if flex is Flex.VERTICAL:
            scale = remaining_height / max(1, total_fraction)
        else:
            scale = float(remaining_height)
        for child in collapsed:
            if isinstance(child.height, float):
                scaled_height = min(remaining_height, int(child.height * scale))
                compute_heights(tree, child, scaled_height)
                remaining_height -= tree.heights[child.uuid]
    else:
        # No height constraint - fractional heights get 0
        for child in collapsed:
            if isinstance(child.height, float):
                compute_heights(tree, child, 0)

    # Compute this element's height based on its height specification
    if isinstance(element.height, int):
        final_height = element.height
    elif isinstance(element.height, float):
        final_height = available_height if available_height else 0
    else:  # None - flexible, size to content
        if isinstance(element, Text):
            content_width = element.get_content_width(tree.widths[element.uuid])
            wrapped = wrap_lines(element.text.replace('\t', ' ' * 8), content_width)
            inner_height = wrapped.count('\n') + 1
        elif flex is Flex.VERTICAL:
            inner_height = sum((tree.heights[c.uuid] for c in collapsed), start=0)
        else:
            inner_height = max((tree.heights[c.uuid] for c in collapsed), default=0)
        final_height = inner_height + element.get_vertical_chrome()

    tree.heights[element.uuid] =  min(available_height, final_height) if available_height is not None else final_height


def compute_offsets(tree: ElementTree, element: Element) -> None:
    """Third pass: compute offsets for all children.

    Offsets are relative to parent, not absolute positions.
    Accumulate widths (horizontal flex) or heights (vertical flex) to determine offsets.
    """
    flex = element.flex if isinstance(element, Box) else Flex.VERTICAL
    collapsed = [x for child in tree.children[element.uuid] for x in collapse(tree, child)]

    # Starting offset accounts for this element's margin, border, and padding
    x_offset = element.margin['left'] + element.border['left'] + element.padding['left']
    y_offset = element.margin['top'] + element.border['top'] + element.padding['top']

    for child in collapsed:
        tree.offsets[child.uuid] = Offset(x=x_offset, y=y_offset)
        # Accumulate in the flex direction
        if flex is Flex.HORIZONTAL:
            x_offset += tree.widths[child.uuid]
        else:  # VERTICAL
            y_offset += tree.heights[child.uuid]
        # Recursively compute offsets for children
        compute_offsets(tree, child)


def render(tree: ElementTree, element: Element, width: int) -> str:
    """Render element and its subtree to a string.

    Note: layout() must be called first to populate tree.sizes.
    """
    collapsed = [x for child in tree.children[element.uuid] for x in collapse(tree, child)]

    # Render children using their pre-computed sizes
    contents = [render(tree, c, tree.widths[c.uuid]) for c in collapsed]

    return element.render(contents, width)

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
    terminal_width = shutil.get_terminal_size().columns
    layout(tree, root, terminal_width)
    initial_render = render(tree, root, terminal_width)
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
