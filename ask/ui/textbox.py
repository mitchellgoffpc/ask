import sys
import tty
import termios
from ask.ui import boxes
from ask.ui.styles import Colors
from ask.ui.cursor import cursor_prev_line, hide_cursor, show_cursor

class TextBox:
    def __init__(self, width=20, height=1, box_style=boxes.SINGLE):
        self.width = width
        self.height = height
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
        else:
            self.content = self.content[:self.cursor_pos] + ch + self.content[self.cursor_pos:]
            self.cursor_pos += 1
        return False

    def render(self):
        top = self.box_style["topLeft"] + self.box_style["top"] * self.width + self.box_style["topRight"]
        bottom = self.box_style["bottomLeft"] + self.box_style["bottom"] * self.width + self.box_style["bottomRight"]

        # Create the content line with a cursor
        display_content = self.content
        if len(display_content) >= self.width:
            # Ensure cursor is visible by adjusting the view
            start_pos = max(0, self.cursor_pos - self.width + 1)
            display_content = display_content[start_pos:start_pos + self.width]
            cursor_display_pos = min(self.cursor_pos - start_pos, self.width - 1)
        else:
            cursor_display_pos = self.cursor_pos

        # Pad the content to fill the width
        display_content = display_content.ljust(self.width)[:self.width]

        # Insert the cursor at the correct position
        content_before_cursor = display_content[:cursor_display_pos]
        cursor_char = display_content[cursor_display_pos:cursor_display_pos + 1] if cursor_display_pos < len(display_content) else ' '
        content_after_cursor = display_content[cursor_display_pos + 1:] if cursor_display_pos < self.width - 1 else ''
        cursor = Colors.INVERSE + cursor_char + Colors.INVERSE_END
        content_line = self.box_style["left"] + content_before_cursor + cursor + content_after_cursor + self.box_style["right"]

        return '\r' + top + '\n\r' + content_line + '\n\r' + bottom + '\n\r'


if __name__ == "__main__":
    textbox = TextBox()
    hide_cursor()
    print(textbox.render(), end='')

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if textbox.handle_input(ch):
                break
            print(cursor_prev_line * 3, end='')  # Move cursor up to beginning of textbox
            print(textbox.render(), end='')
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        show_cursor()

    print(f"\nFinal text: {textbox.content}")
