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
from types import MethodType
from uuid import UUID

from ask.ui.core.components import Component, get_rendered_width, dirty, nodes, parents, children
from ask.ui.core.cursor import hide_cursor, show_cursor, erase_line, cursor_up
from ask.ui.core.styles import Flex

# Context manager to set O_NONBLOCK on a file descriptor
@contextmanager
def nonblocking(fd):
    original_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    try:
        fcntl.fcntl(fd, fcntl.F_SETFL, original_fl | os.O_NONBLOCK)
        yield
    finally:
        fcntl.fcntl(fd, fcntl.F_SETFL, original_fl)

# Utility function to print the component tree
def print_node(uuid: UUID, level: int = 0) -> None:
    component = nodes[uuid]
    print('  ' * level + f'└─ {component.__class__.__name__}')
    for child in children.get(uuid, []):
        if child:  # Skip None values
            print_node(child.uuid, level + 1)

# Add a component and all its children to the tree
def mount(component):
    nodes[component.uuid] = component
    contents = component.contents()
    children[component.uuid] = contents
    component.handle_mount()
    for child in contents:
        if child:
            parents[child.uuid] = component
            mount(child)

# Remove a component and all its children from the tree
def unmount(component):
    for child in children[component.uuid]:
        if child:
            unmount(child)
    component.handle_unmount()
    del children[component.uuid]
    del nodes[component.uuid]
    del parents[component.uuid]

# Update a component's subtree
def update(uuid, component, new_to_old):
    new_contents = component.contents()
    old_contents = children.get(uuid, [])

    for i, (old_child, new_child) in enumerate(zip_longest(old_contents, new_contents)):
        if new_child:
            new_to_old[new_child] = old_child
        if not old_child and not new_child:
            continue
        elif not old_child:
            # New child added
            if i >= len(children[uuid]):
                children[uuid].append(new_child)
            else:
                children[uuid][i] = new_child
            parents[new_child.uuid] = component
            nodes[new_child.uuid] = new_child
            mount(new_child)
        elif not new_child:
            # Child removed
            unmount(old_child)
            children[uuid][i] = None
        elif old_child.__class__ is not new_child.__class__:
            # Class changed, replace the child
            unmount(old_child)
            children[uuid][i] = new_child
            parents[new_child.uuid] = component
            nodes[new_child.uuid] = new_child
            mount(new_child)
        else:
            if old_child.props != new_child.props:
                # Same class but props changed, update the props and re-render
                old_child.handle_update(new_child.props)
                old_child.props = new_child.props.copy()
                # Since the new nodes will be discarded after the update, we need to rebind all methods to the original nodes
                # This is really janky and probably doesn't work for things like decorators, but I don't have any better ideas atm
                for k, v in old_child.props.items():
                    if callable(v) and hasattr(v, '__self__') and v.__self__ in new_to_old:
                        old_child.props[k] = MethodType(v.__func__, new_to_old[v.__self__])

            # TODO: Avoid updating parts of the tree that haven't changed
            new_child.state.state = old_child.state.state.copy()
            update(old_child.uuid, new_child, new_to_old)


# Render a component and its subtree to a string
def render(component, width):
    remaining_width = component.get_content_width(width)
    flex = component.props.get('flex') or Flex.VERTICAL
    renders = {}
    for i, c in enumerate(children[component.uuid]):
        if c and isinstance(c.props['width'], int) and remaining_width > 0:
            renders[i] = render(c, c.props['width'])
            remaining_width -= c.rendered_width if flex is Flex.HORIZONTAL else 0
    for i, c in enumerate(children[component.uuid]):
        if c and c.props['width'] is None and remaining_width > 0:
            renders[i] = render(c, remaining_width)
            remaining_width -= c.rendered_width if flex is Flex.HORIZONTAL else 0

    if flex is Flex.HORIZONTAL:
        scale = remaining_width / max(1, sum(c.props['width'] for c in children[component.uuid] if c and isinstance(c.props['width'], float)))
    elif flex is Flex.VERTICAL:
        scale = remaining_width
    for i, c in enumerate(children[component.uuid]):
        if c and isinstance(c.props['width'], float) and remaining_width > 0:
            renders[i] = render(c, min(remaining_width, int(c.props['width'] * scale)))
            remaining_width -= c.rendered_width

    contents = [c for _, c in sorted(renders.items())]
    rendered = component.render(contents, width)
    component.rendered_width = get_rendered_width(rendered)
    return rendered

# Get the depth of a node
def depth(node, root):
    depth = 0
    while node is not root:
        node = parents[node.uuid]
        depth += 1
    return depth

# Propogate input to a component and its subtree
def propogate(node, value, handler='handle_raw_input'):
    getattr(node, handler)(value)
    for child in children.get(node.uuid, []):
        if child:
            propogate(child, value, handler)


# Main render loop

async def render_root(root: Component) -> None:
    hide_cursor()

    mount(root)
    initial_render = render(root, shutil.get_terminal_size().columns)
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
                propogate(root, sequence, 'handle_raw_input')

            # Check for dirty components
            if not dirty:
                await asyncio.sleep(0.01)
                continue
            for uuid in sorted(dirty, key=lambda uuid: depth(nodes[uuid], root)):  # start at the top and work downwards
                if uuid in nodes:
                    update(uuid, nodes[uuid], {})
            dirty.clear()

            # Re-render the tree
            terminal_size = shutil.get_terminal_size()
            new_render_lines = render(root, terminal_size.columns).split('\n')

            # Check if we need to clear screen due to large difference in output size
            if len(previous_render_lines) - len(new_render_lines) > min(terminal_size.lines / 2, terminal_size.lines - 20):
                sys.stdout.write('\033[2J\033[H')
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
                if len(new_line) < len(prev_line):
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
