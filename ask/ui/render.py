import select
import shutil
import sys
import termios
import tty
from itertools import zip_longest
from uuid import UUID

from ask.ui.components import Component, get_rendered_width, dirty, nodes, parents, children, renders, threads
from ask.ui.cursor import hide_cursor, show_cursor, erase_line, cursor_up
from ask.ui.styles import Flex

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
        parents[child.uuid] = component
        mount(child)

# Remove a component and all its children from the tree
def unmount(component):
    for child in children[component.uuid]:
        unmount(child)
    component.handle_unmount()
    del children[component.uuid]
    del nodes[component.uuid]
    del parents[component.uuid]
    del renders[component.uuid]

# Update a component's subtree
def update(uuid, component):
    new_contents = component.contents()
    old_contents = children.get(uuid, [])

    for i, (old_child, new_child) in enumerate(zip_longest(old_contents, new_contents)):
        if not old_child and not new_child:
            continue
        elif not old_child:
            # New child added
            children[uuid].append(new_child)
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
        elif old_child.props != new_child.props:
            # Same class but props changed, update the props and re-render
            old_child.handle_update(new_child.props)
            old_child.props = new_child.props.copy()
            update(old_child.uuid, new_child)
        else:
            update(old_child.uuid, new_child)

    # Remove trailing None children
    while children[uuid] and not children[uuid][-1]:
        children[uuid].pop()

# Render a component and its subtree to a string
def render(component, width):
    content_width = component.get_content_width(width)
    childs = [c for c in children[component.uuid] if c]
    static_renders = {i: render(c, content_width) for i, c in enumerate(childs) if c.props['width'] is None}
    fixed_renders = {i: render(c, c.props['width']) for i, c in enumerate(childs) if isinstance(c.props['width'], int)}
    if component.props.get('flex') is Flex.HORIZONTAL:
        remaining_width = content_width - sum(childs[i].rendered_width for i in (*static_renders.keys(), *fixed_renders.keys()))
        scale = remaining_width / max(1, sum(c.props['width'] for c in childs if isinstance(c.props['width'], float)))  # scale down widths if necessary
    elif component.props.get('flex') is Flex.VERTICAL:
        scale = content_width
    dynamic_renders = {i: render(c, min(content_width, int(c.props['width'] * scale))) for i, c in enumerate(childs) if isinstance(c.props['width'], float)}
    contents = [c for _, c in sorted((static_renders | fixed_renders | dynamic_renders).items())]
    renders[component.uuid] = component.render(contents, width)
    component.rendered_width = get_rendered_width(renders[component.uuid])
    return renders[component.uuid]

# Get the depth of a node
def depth(node, root):
    depth = 0
    while node is not root:
        node = parents[node.uuid]
        depth += 1
    return depth

# Propogate input to a component and its subtree
def propogate(node, value, handler='handle_input'):
    getattr(node, handler)(value)
    for child in children.get(node.uuid, []):
        if child:
            propogate(child, value, handler)


# Main render loop

def render_root(root: Component) -> None:
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
            # Check for input with 100ms timeout
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if ready:
                # Read input character and handle escape sequences
                ch = sys.stdin.read(1)
                if ch == '\x03':  # Ctrl+C
                    sys.exit()

                # Handle escape sequences and regular input
                sequence = ch
                if ch == '\x1b':  # Escape sequence
                    sequence += sys.stdin.read(1)
                    if sequence[-1] == '[':
                        while not (ch := sys.stdin.read(1)).isalpha():
                            sequence += ch
                        sequence += ch
                propogate(root, sequence, 'handle_input')

            # Check for completed threads
            for uuid in list(threads.keys()):
                if not threads[uuid].is_alive():
                    del threads[uuid]

            # Check for dirty components
            if not dirty:
                continue
            for uuid in sorted(dirty, key=lambda uuid: depth(nodes[uuid], root)):  # start at the top and work downwards
                update(uuid, nodes[uuid])
            dirty.clear()

            # Re-render the tree
            new_render_lines = render(root, shutil.get_terminal_size().columns).split('\n')

            # Pad new render to match the number of previous lines
            max_lines = max(len(previous_render_lines), len(new_render_lines))
            new_render_lines.extend([''] * (max_lines - len(new_render_lines)))

            # If there are unchanged leading lines, move cursor to the first changed line
            line_diffs = zip_longest(previous_render_lines, new_render_lines, fillvalue='')
            first_diff_idx = next((i for i, (prev, new) in enumerate(line_diffs) if prev != new), None)
            if first_diff_idx is None:
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

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        show_cursor()
