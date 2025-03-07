import sys
import tty
import termios
from ask.ui.textbox import TextBox
from ask.ui.cursor import hide_cursor, show_cursor, erase_line, cursor_up

if __name__ == "__main__":
    textbox = TextBox()
    hide_cursor()
    initial_render = textbox.render()
    previous_render_lines = initial_render.splitlines()
    print('\n\r'.join(previous_render_lines))

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == '\x03':  # Ctrl+C
                sys.exit()
            textbox.handle_input(ch)
            sys.stdout.write(cursor_up(len(previous_render_lines)))
            new_render = textbox.render()
            new_render_lines = new_render.splitlines()

            # Pad new render to match the number of previous lines
            max_lines = max(len(previous_render_lines), len(new_render_lines))
            new_render_lines.extend([''] * (max_lines - len(new_render_lines)))
            previous_render_lines.extend([''] * (max_lines - len(previous_render_lines)))

            # Render current state
            for prev_line, new_line in zip(previous_render_lines, new_render_lines):
                sys.stdout.write('\r')
                if len(new_line) < len(prev_line):  # Clear if the new line is shorter
                    sys.stdout.write(erase_line)
                sys.stdout.write(new_line + '\n\r')
            sys.stdout.flush()

            previous_render_lines = new_render_lines
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        show_cursor()
