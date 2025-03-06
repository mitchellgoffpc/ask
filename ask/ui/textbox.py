import sys
import tty
import termios
from ask.ui import boxes
from ask.ui.styles import Colors
from ask.ui.cursor import hide_cursor, show_cursor, erase_line, cursor_up

class TextBox:
    def __init__(self, width=20, box_style=boxes.SINGLE):
        self.width = width
        self.box_style = box_style
        self.content = ''
        self.cursor_pos = 0

    def handle_input(self, ch):
        if ch == '\n':
            return True
        elif ch == '\x03':  # Ctrl+C
            sys.exit()
        elif ch == '\x7f':  # Backspace
            if self.cursor_pos > 0:
                self.content = self.content[:self.cursor_pos - 1] + self.content[self.cursor_pos:]
                self.cursor_pos -= 1
        elif ch == '\x1b':  # Escape sequence (arrow keys)
            next_ch = sys.stdin.read(1)
            if next_ch == '[':
                direction = sys.stdin.read(1)
                if direction == 'D':  # Left arrow
                    if self.cursor_pos > 0:
                        self.cursor_pos -= 1
                elif direction == 'C':  # Right arrow
                    if self.cursor_pos < len(self.content):
                        self.cursor_pos += 1
                elif direction == 'A':  # Up arrow
                    current_line, current_col = self.get_cursor_line_col()
                    if current_line > 0:
                        line_start = self.get_line_start_position(current_line - 1)
                        self.cursor_pos = min(line_start + current_col, self.get_line_end_position(current_line - 1))
                elif direction == 'B':  # Down arrow
                    current_line, current_col = self.get_cursor_line_col()
                    if current_line < self.get_total_lines() - 1:
                        line_start = self.get_line_start_position(current_line + 1)
                        self.cursor_pos = min(line_start + current_col, self.get_line_end_position(current_line + 1))
        else:
            self.content = self.content[:self.cursor_pos] + ch + self.content[self.cursor_pos:]
            self.cursor_pos += 1
        return False

    def wrap_content(self):
        lines = []
        start = 0
        while start < len(self.content):
            end = min(start + self.width, len(self.content))
            lines.append(self.content[start:end])
            start = end
        if not lines or len(lines[-1]) == self.width:
            lines.append('')
        return lines

    def get_cursor_line_col(self):
        line = self.cursor_pos // self.width
        col = self.cursor_pos % self.width
        return line, col

    def get_total_lines(self):
        return (len(self.content) + self.width - 1) // self.width

    def get_line_start_position(self, line):
        return line * self.width

    def get_line_end_position(self, line):
        return min((line + 1) * self.width, len(self.content))

    def render(self):
        lines = self.wrap_content()
        top = self.box_style["topLeft"] + self.box_style["top"] * self.width + self.box_style["topRight"]
        bottom = self.box_style["bottomLeft"] + self.box_style["bottom"] * self.width + self.box_style["bottomRight"]

        content_lines = ''
        cursor_line, cursor_col = self.get_cursor_line_col()
        for idx, line_content in enumerate(lines):
            line_content = line_content.ljust(self.width)
            if idx == cursor_line:
                content_before_cursor = line_content[:cursor_col]
                cursor_char = line_content[cursor_col:cursor_col + 1]
                content_after_cursor = line_content[cursor_col + 1:]
                cursor = Colors.INVERSE + cursor_char + Colors.INVERSE_END
                full_line = self.box_style["left"] + content_before_cursor + cursor + content_after_cursor + self.box_style["right"]
            else:
                full_line = self.box_style["left"] + line_content + self.box_style["right"]
            content_lines += '\n' + full_line

        return top + content_lines + '\n' + bottom


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
            if textbox.handle_input(ch):
                break
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
