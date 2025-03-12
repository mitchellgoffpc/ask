import sys
import tty
import termios
from uuid import UUID
from itertools import zip_longest
from ask.ui.styles import Styles, Colors
from ask.ui.components import Component, dirty
from ask.ui.cursor import hide_cursor, show_cursor, erase_line, cursor_up

def render_root(root: Component) -> None:
    hide_cursor()

    nodes: dict[UUID, Component] = {}
    parents: dict[UUID, Component] = {}
    children: dict[UUID, list[Component]] = {}
    renders: dict[UUID, str] = {}

    # Add a component and all its children to the tree
    def mount(component):
        dirty.discard(component.uuid)
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
        dirty.discard(component.uuid)

    def render(component):
        contents = [render(child) for child in children[component.uuid]]
        renders[component.uuid] = component.render(contents)
        return renders[component.uuid]

    def propogate(node, value, handler='handle_input'):
        getattr(node, handler)(value)
        for child in children.get(node.uuid, []):
            propogate(child, value, handler)

    mount(root)
    initial_render = render(root)
    previous_render_lines = initial_render.split('\n')
    print('\n\r'.join(previous_render_lines))

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == '\x03':  # Ctrl+C
                sys.exit()
            propogate(root, ch, 'handle_input')
            if not dirty:
                continue

            # Process dirty nodes and update the tree
            while len(dirty):
                node_uuid = dirty.pop()
                component = nodes[node_uuid]
                dirty.discard(component.uuid)
                new_contents = component.contents()
                old_contents = children.get(component.uuid, [])

                for old_child, new_child in zip_longest(old_contents, new_contents):
                    if old_child is None:
                        # New child added
                        children[component.uuid].append(new_child)
                        parents[new_child.uuid] = component
                        nodes[new_child.uuid] = new_child
                        dirty.add(new_child.uuid)
                        mount(new_child)
                    elif new_child is None:
                        # Child removed
                        unmount(old_child)
                    elif old_child.__class__ is not new_child.__class__:
                        # Class changed, replace the child
                        unmount(old_child)
                        children[component.uuid][old_contents.index(old_child)] = new_child
                        parents[new_child.uuid] = component
                        nodes[new_child.uuid] = new_child
                        dirty.add(new_child.uuid)
                        mount(new_child)
                    elif old_child.props != new_child.props:
                        # Same class but props changed, update props and mark dirty
                        old_child.props = new_child.props.copy()
                        dirty.add(old_child.uuid)

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


if __name__ == "__main__":
    from pathlib import Path
    from ask.ui.components import Component, Box, Text
    from ask.ui.textbox import PromptTextBox
    from ask.ui.commands import CommandsList

    class App(Component):
        def __init__(self):
            super().__init__()
            self.state.update({'text': ''})

        def contents(self) -> list[Component]:
            return [
                Box(padding={'left': 1, 'right': 1}, margin={'bottom': 1}, border_color=Colors.HEX('#BE5103'))[
                    Text(f"{Colors.hex('✻', '#BE5103')} Welcome to {Styles.bold('Ask')}!", margin={'bottom': 1}),
                    Text(Colors.hex("  /help for help", '#999999'), margin={'bottom': 1}),
                    Text(Colors.hex(f"  cwd: {Path.cwd()}", '#999999')),
                ],
                PromptTextBox(border_color=Colors.HEX('#4A4A4A'), placeholder='Try "how do I log an error?"', handle_change=lambda x: self.state.update({'text': x})),
                Text(Colors.hex('! for bash mode · / for commands', '#999999'), margin={'left': 2}),
                CommandsList(prefix=self.state['text']),
            ]

    app = App()
    render_root(app)
