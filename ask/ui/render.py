import sys
import tty
import termios
from ask.ui.styles import Styles, Colors
from ask.ui.components import Component
from ask.ui.cursor import hide_cursor, show_cursor, erase_line, cursor_up

def render(*elements: Component) -> None:
    hide_cursor()
    initial_renders = [element.render() for element in elements]
    previous_render_lines = []
    for render_output in initial_renders:
        previous_render_lines.extend(render_output.split('\n'))
    print('\n\r'.join(previous_render_lines))

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == '\x03':  # Ctrl+C
                sys.exit()
            for element in elements:
                element.handle_input(ch)

            output = ''
            new_renders = [element.render() for element in elements]
            new_render_lines = []
            for render_output in new_renders:
                new_render_lines.extend(render_output.split('\n'))

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
    from ask.ui.components import Box, Text
    from ask.ui.textbox import PromptTextBox
    render(
        Box(padding={'left': 1, 'right': 1}, margin={'bottom': 1}, border_color=Colors.HEX('#BE5103'))[
            Text(f"{Colors.hex('✻', '#BE5103')} Welcome to {Styles.bold('Ask')}!", margin={'bottom': 1}),
            Text(Colors.hex("  /help for help", '#999999'), margin={'bottom': 1}),
            Text(Colors.hex(f"  cwd: {Path.cwd()}", '#999999')),
        ],
        PromptTextBox(border_color=Colors.HEX('#4A4A4A'), placeholder='Try "how do I log an error?"'),
    )
