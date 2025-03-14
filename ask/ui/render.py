import sys
import tty
import termios
from uuid import UUID
from itertools import zip_longest
from ask.ui.styles import Styles, Colors
from ask.ui.components import Component, dirty
from ask.ui.cursor import hide_cursor, show_cursor, erase_line, cursor_up

nodes: dict[UUID, Component] = {}
parents: dict[UUID, Component] = {}
children: dict[UUID, list[Component | None]] = {}
renders: dict[UUID, str] = {}

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
    for child in contents:
        parents[child.uuid] = component
        mount(child)

# Remove a component and all its children from the tree
def unmount(component):
    for child in children[component.uuid]:
        unmount(child)
    del children[component.uuid]
    del nodes[component.uuid]
    del parents[component.uuid]
    del renders[component.uuid]

# Update a component's subtree
def update(component):
    new_contents = component.contents()
    old_contents = children.get(component.uuid, [])

    for i, (old_child, new_child) in enumerate(zip_longest(old_contents, new_contents)):
        if not old_child and not new_child:
            continue
        elif not old_child:
            # New child added
            children[component.uuid].append(new_child)
            parents[new_child.uuid] = component
            nodes[new_child.uuid] = new_child
            mount(new_child)
        elif not new_child:
            # Child removed
            unmount(old_child)
            children[component.uuid][i] = None
        elif old_child.__class__ is not new_child.__class__:
            # Class changed, replace the child
            unmount(old_child)
            children[component.uuid][i] = new_child
            parents[new_child.uuid] = component
            nodes[new_child.uuid] = new_child
            mount(new_child)
        elif old_child.props != new_child.props:
            # Same class but props changed, update props and mark dirty
            old_child.props = new_child.props.copy()
            update(old_child)

    # Remove trailing None children
    while children[component.uuid] and not children[component.uuid][-1]:
        children[component.uuid].pop()

# Render a component and its subtree to a string
def render(component):
    contents = [render(child) for child in children[component.uuid] if child]
    renders[component.uuid] = component.render(contents)
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
    initial_render = render(root)
    previous_render_lines = initial_render.split('\n')
    print('\n\r'.join(previous_render_lines))

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            # Read input character and handle escape sequences
            ch = sys.stdin.read(1)
            if ch == '\x03':  # Ctrl+C
                sys.exit()

            # Handle escape sequences and regular input
            sequence = sequence = ch
            if ch == '\x1b':  # Escape sequence
                sequence += sys.stdin.read(1)
                if sequence[-1] == '[':
                    while not (ch := sys.stdin.read(1)).isalpha():
                        sequence += ch
                    sequence += ch
            propogate(root, sequence, 'handle_input')

            if not dirty:
                continue
            for uuid in sorted(dirty, key=lambda uuid: depth(nodes[uuid], root)):  # start at the top and work downwards
                update(nodes[uuid])
            dirty.clear()

            # Re-render the tree
            new_render_lines = render(root).split('\n')

            # Pad new render to match the number of previous lines
            max_lines = max(len(previous_render_lines), len(new_render_lines))
            new_render_lines.extend([''] * (max_lines - len(new_render_lines)))

            # If there are unchanged leading lines, move cursor to the first changed line
            first_diff_idx = next((i for i, (prev, new) in enumerate(zip_longest(previous_render_lines, new_render_lines, fillvalue='')) if prev != new), None)
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


# Entry point for testing

if __name__ == "__main__":
    from pathlib import Path
    from ask.ui.styles import Theme
    from ask.ui.components import Component, Box, Text
    from ask.ui.textbox import PromptTextBox
    from ask.ui.commands import CommandsList

    class App(Component):
        initial_state = {'text': '', 'bash_mode': False}

        def handle_change(self, value: str) -> None:
            self.state.update({'text': value})

        def handle_set_bash_mode(self, value: bool) -> None:
            self.state.update({'bash_mode': value})

        def contents(self) -> list[Component]:
            return [
                Box(padding={'left': 1, 'right': 1}, margin={'bottom': 1}, border_color=Colors.HEX(Theme.ORANGE))[
                    Text(f"{Colors.hex('✻', Theme.ORANGE)} Welcome to {Styles.bold('Ask')}!", margin={'bottom': 1}),
                    Text(Colors.hex("  /help for help", Theme.GRAY), margin={'bottom': 1}),
                    Text(Colors.hex(f"  cwd: {Path.cwd()}", Theme.GRAY)),
                ],
                PromptTextBox(
                    placeholder='Try "how do I log an error?"',
                    bash_mode=self.state['bash_mode'],
                    handle_change=self.handle_change,
                    handle_set_bash_mode=self.handle_set_bash_mode),
                CommandsList(prefix=self.state['text'], bash_mode=self.state['bash_mode']),
            ]

    app = App()
    render_root(app)
