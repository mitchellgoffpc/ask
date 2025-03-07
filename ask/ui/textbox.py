import sys
import shutil
from ask.ui.box import Borders
from ask.ui.styles import Colors

class TextBox:
    def __init__(self, width=None, border_style=Borders.SINGLE):
        self._width = width
        self.border_style = border_style
        self.content = ''
        self.cursor_pos = 0

    @property
    def width(self):
        return self._width or shutil.get_terminal_size().columns - 2  # Adjusting for box borders

    def handle_input(self, ch):
        if ch == '\r':  # Enter
            ch = '\n'
        if ch == '\x7f':  # Backspace
            if self.cursor_pos > 0:
                self.content = self.content[:self.cursor_pos - 1] + self.content[self.cursor_pos:]
                self.cursor_pos -= 1
        elif ch == '\x1b':  # Escape sequence (arrow keys)
            next_ch = sys.stdin.read(1)
            if next_ch == '[':
                direction = sys.stdin.read(1)
                current_line, current_col = self.get_cursor_line_col()
                if direction == 'D' and self.cursor_pos > 0:  # Left arrow
                    self.cursor_pos -= 1
                elif direction == 'C' and self.cursor_pos < len(self.content):  # Right arrow
                    self.cursor_pos += 1
                elif direction == 'A' and current_line > 0:  # Up arrow
                    line_start = self.get_line_start_position(current_line - 1)
                    self.cursor_pos = min(line_start + current_col, self.get_line_end_position(current_line - 1))
                elif direction == 'B' and current_line < self.get_total_lines() - 1:  # Down arrow
                    line_start = self.get_line_start_position(current_line + 1)
                    self.cursor_pos = min(line_start + current_col, self.get_line_end_position(current_line + 1))
        else:
            self.content = self.content[:self.cursor_pos] + ch + self.content[self.cursor_pos:]
            self.cursor_pos += 1

    def get_cursor_line_col(self):
        paragraphs = self.content[:self.cursor_pos].split('\n')
        line = 0
        for paragraph in paragraphs[:-1]:
            paragraph_length = len(paragraph)
            num_lines = (paragraph_length + self.width - 1) // self.width or 1
            line += num_lines
        last_paragraph = paragraphs[-1]
        line += len(last_paragraph) // self.width
        col = len(last_paragraph) % self.width
        return line, col

    def get_total_lines(self):
        return (len(self.content) + self.width - 1) // self.width

    def get_line_start_position(self, line):
        return line * self.width

    def get_line_end_position(self, line):
        return min((line + 1) * self.width, len(self.content))

    def wrap_content(self):
        lines = []
        paragraphs = self.content.split('\n')
        for paragraph in paragraphs:
            if paragraph == '':
                lines.append('')
            else:
                start = 0
                while start < len(paragraph):
                    end = min(start + self.width, len(paragraph))
                    lines.append(paragraph[start:end])
                    start = end
        if not lines or len(lines[-1]) == self.width:
            lines.append('')
        return lines

    def render(self):
        top = self.border_style["topLeft"] + self.border_style["top"] * self.width + self.border_style["topRight"]
        bottom = self.border_style["bottomLeft"] + self.border_style["bottom"] * self.width + self.border_style["bottomRight"]
        lines = self.wrap_content()

        content_lines = ''
        cursor_line, cursor_col = self.get_cursor_line_col()
        for idx, line_content in enumerate(lines):
            line_content = line_content.ljust(self.width)
            if idx == cursor_line:
                content_before_cursor = line_content[:cursor_col]
                cursor_char = line_content[cursor_col:cursor_col + 1]
                content_after_cursor = line_content[cursor_col + 1:]
                cursor = Colors.INVERSE + cursor_char + Colors.INVERSE_END
                full_line = self.border_style["left"] + content_before_cursor + cursor + content_after_cursor + self.border_style["right"]
            else:
                full_line = self.border_style["left"] + line_content + self.border_style["right"]
            content_lines += '\n' + full_line

        return top + content_lines + '\n' + bottom
