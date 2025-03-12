import sys
import tty
import termios
from ask.ui.styles import Styles, Colors
from ask.ui.components import Component, dirty
from ask.ui.cursor import hide_cursor, show_cursor, erase_line, cursor_up

def render_root(root: Component) -> None:
    hide_cursor()

    nodes = {}
    parents = {}
    children = {}
    renders = {}

    def build_tree(component):
        dirty.discard(component.uuid)
        nodes[component.uuid] = component
        contents = component.contents()
        children[component.uuid] = contents
        for child in contents:
            parents[child.uuid] = component
            build_tree(child)

    def render(component):
        contents = [render(child) for child in children[component.uuid]]
        renders[component.uuid] = component.render(contents)
        return renders[component.uuid]

    def propogate(node, value, handler='handle_input'):
        getattr(node, handler)(value)
        for child in children.get(node.uuid, []):
            propogate(child, value, handler)

    build_tree(root)
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

            output = ''
            new_render_lines = render(root).split('\n')

            # Pad new render to match the number of previous lines
            max_lines = max(len(previous_render_lines), len(new_render_lines))
            new_render_lines.extend([''] * (max_lines - len(new_render_lines)))
            previous_render_lines.extend([''] * (max_lines - len(previous_render_lines)))

            # If there are unchanged leading lines, move cursor to the first changed line
            first_diff_idx = next((i for i, (prev, new) in enumerate(zip(previous_render_lines, new_render_lines)) if prev != new), None)
            if first_diff_idx is None:
                continue

            output += cursor_up(len(previous_render_lines) - first_diff_idx)
            for prev_line, new_line in zip(previous_render_lines[first_diff_idx:], new_render_lines[first_diff_idx:]):
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
