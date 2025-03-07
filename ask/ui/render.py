import sys
import tty
import termios
from ask.ui.textbox import TextBox
from ask.ui.cursor import hide_cursor, show_cursor, erase_line, cursor_up

def render(*elements):
    hide_cursor()
    initial_renders = [element.render() for element in elements]
    previous_render_lines = []
    for render_output in initial_renders:
        previous_render_lines.extend(render_output.splitlines())
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
            sys.stdout.write(cursor_up(len(previous_render_lines)))
            new_renders = [element.render() for element in elements]
            new_render_lines = []
            for render_output in new_renders:
                new_render_lines.extend(render_output.splitlines())

            # Pad new render to match the number of previous lines
            max_lines = max(len(previous_render_lines), len(new_render_lines))
            new_render_lines.extend([''] * (max_lines - len(new_render_lines)))
            previous_render_lines.extend([''] * (max_lines - len(previous_render_lines)))

            # Render current state
            for prev_line, new_line in zip(previous_render_lines, new_render_lines):
                sys.stdout.write('\r')
                if len(new_line) < len(prev_line):
                    sys.stdout.write(erase_line)
                sys.stdout.write(new_line + '\n\r')
            sys.stdout.flush()

            previous_render_lines = new_render_lines
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        show_cursor()


if __name__ == "__main__":
    textbox = TextBox()
    render(textbox)
