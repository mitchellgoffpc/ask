import sys
from ask.ui.components import Box, Size
from ask.ui.styles import Styles, Colors, Borders, BorderStyle

class TextBox(Box):
    def __init__(self, width: Size = 1.0, border_color: str | None = None, border_style: BorderStyle = Borders.ROUND):
        super().__init__(width=width, border_color=border_color, border_style=border_style)
        assert self.content_width > 0, "TextBox width must be specified"
        self.content: str = ''
        self.cursor_pos: int = 0

    def handle_input(self, ch: str) -> None:
        if ch == '\r':  # Enter
            ch = '\n'
        if ch == '\x7f':  # Backspace
            if self.cursor_pos > 0:
                self.content = self.content[:self.cursor_pos - 1] + self.content[self.cursor_pos:]
                self.cursor_pos -= 1
        elif ch == '\x1b':  # Escape sequence (arrow keys) or Alt key combinations
            next_ch = sys.stdin.read(1)
            if next_ch == '[':  # Arrow keys
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
            elif next_ch == '\x7f':  # Alt+Backspace, delete word
                if self.cursor_pos > 0:
                    pos = self.cursor_pos - 1
                    while pos >= 0 and self.content[pos].isspace():
                        pos -= 1
                    while pos >= 0 and not self.content[pos].isspace():
                        pos -= 1
                    self.content = self.content[:pos + 1] + self.content[self.cursor_pos:]
                    self.cursor_pos = pos + 1
        else:
            self.content = self.content[:self.cursor_pos] + ch + self.content[self.cursor_pos:]
            self.cursor_pos += 1

    def get_cursor_line_col(self) -> tuple[int, int]:
        paragraphs = self.content[:self.cursor_pos].split('\n')
        line = 0
        for paragraph in paragraphs[:-1]:
            paragraph_length = len(paragraph)
            num_lines = (paragraph_length + self.content_width - 1) // self.content_width
            line += num_lines
        last_paragraph = paragraphs[-1]
        line += len(last_paragraph) // self.content_width
        col = len(last_paragraph) % self.content_width
        return line, col

    def get_total_lines(self) -> int:
        return (len(self.content) + self.content_width - 1) // self.content_width

    def get_line_start_position(self, line: int) -> int:
        return line * self.content_width

    def get_line_end_position(self, line: int) -> int:
        return min((line + 1) * self.content_width, len(self.content))

    def wrap_content(self) -> list[str]:
        lines = []
        paragraphs = self.content.split('\n')
        for paragraph in paragraphs:
            if paragraph == '':
                lines.append('')
            else:
                start = 0
                while start < len(paragraph):
                    end = min(start + self.content_width, len(paragraph))
                    lines.append(paragraph[start:end])
                    start = end
        if not lines or len(lines[-1]) == self.content_width:
            lines.append('')
        return lines

    def render_contents(self) -> str:
        lines = self.wrap_content()
        cursor_line, cursor_col = self.get_cursor_line_col()

        result_lines = []
        for idx, line_content in enumerate(lines):
            line_content = line_content.ljust(self.content_width)
            if idx == cursor_line:
                content_before_cursor = line_content[:cursor_col]
                cursor_char = line_content[cursor_col:cursor_col + 1]
                content_after_cursor = line_content[cursor_col + 1:]
                line_content = content_before_cursor + Styles.inverse(cursor_char) + content_after_cursor
            result_lines.append(line_content)

        return '\n'.join(result_lines)


class PromptTextBox(TextBox):
    def __init__(self, width: Size = 1.0, border_color: str | None = None, border_style: BorderStyle = Borders.ROUND, placeholder: str = ""):
        super().__init__(width=width, border_color=border_color, border_style=border_style)
        self.placeholder = placeholder

    @property
    def content_width(self) -> int:
        return max(0, self.box_width - 5)  # 2 spaces for borders, 3 spaces for prompt arrow

    def render_contents(self) -> str:
        if not self.content and self.placeholder:
            return f" > {Styles.inverse(self.placeholder[0])}{Colors.hex(self.placeholder[1:], '#999999')}"
        lines = super().render_contents().split('\n')
        lines = [f" > {line}" if i == 0 else f"   {line}" for i, line in enumerate(lines)]
        return '\n'.join(lines)
