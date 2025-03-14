from typing import Callable
from ask.ui.components import Box, Size
from ask.ui.styles import Styles, Colors, Borders, BorderStyle, Theme

TextCallback = Callable[[str], None]
BoolCallback = Callable[[bool], None]

class TextBox(Box):
    leaf = True
    initial_state = {'content': '', 'cursor_pos': 0}

    def __init__(
        self,
        width: Size = 1.0,
        border_color: str | None = None,
        border_style: BorderStyle = Borders.ROUND,
        handle_change: TextCallback | None = None,
        placeholder: str = "",
        **props
    ):
        super().__init__(width=width, border_color=border_color, border_style=border_style, handle_change=handle_change, placeholder=placeholder, **props)
        assert self.content_width > 0, "TextBox width must be specified"

    def handle_input(self, ch: str) -> None:
        cursor_pos = self.state['cursor_pos']
        content = self.state['content']
        if ch == '\r':  # Enter
            ch = '\n'
        if ch == '\x7f':  # Backspace
            if cursor_pos > 0:
                content = content[:cursor_pos - 1] + content[cursor_pos:]
                cursor_pos -= 1
        elif ch.startswith('\x1b'):  # Escape sequence
            if ch.startswith('\x1b['):  # Arrow keys
                direction = ch[2:]
                current_line, current_col = self.get_cursor_line_col()
                if direction == 'D' and cursor_pos > 0:  # Left arrow
                    cursor_pos -= 1
                elif direction == 'C' and cursor_pos < len(content):  # Right arrow
                    cursor_pos += 1
                elif direction == 'A' and current_line > 0:  # Up arrow
                    line_start = self.get_line_start_position(current_line - 1)
                    cursor_pos = min(line_start + current_col, self.get_line_end_position(current_line - 1))
                elif direction == 'B' and current_line < self.get_total_lines() - 1:  # Down arrow
                    line_start = self.get_line_start_position(current_line + 1)
                    cursor_pos = min(line_start + current_col, self.get_line_end_position(current_line + 1))
            elif ch == '\x1b\x7f' and cursor_pos > 0:  # Alt+Backspace, delete word
                pos = cursor_pos - 1
                while pos >= 0 and content[pos].isspace():
                    pos -= 1
                while pos >= 0 and not content[pos].isspace():
                    pos -= 1
                content = content[:pos + 1] + content[cursor_pos:]
                cursor_pos = pos + 1
        else:  # Regular character
            content = content[:cursor_pos] + ch + content[cursor_pos:]
            cursor_pos += 1

        if self.props['handle_change'] and content != self.state['content']:
            self.props['handle_change'](content)
        self.state.update({'content': content, 'cursor_pos': cursor_pos})

    def get_cursor_line_col(self) -> tuple[int, int]:
        paragraphs = self.state['content'][:self.state['cursor_pos']].split('\n')
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
        return (len(self.state['content']) + self.content_width - 1) // self.content_width

    def get_line_start_position(self, line: int) -> int:
        return line * self.content_width

    def get_line_end_position(self, line: int) -> int:
        return min((line + 1) * self.content_width, len(self.state['content']))

    def wrap_content(self) -> list[str]:
        lines = []
        paragraphs = self.state['content'].split('\n')
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
        if not self.state['content'] and self.props['placeholder']:
            return Styles.inverse(self.props['placeholder'][0]) + Colors.hex(self.props['placeholder'][1:], '#999999')

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

    def render(self, _: list[str]) -> str:
        return super().render([self.render_contents()])


class PromptTextBox(TextBox):
    def __init__(self, bash_mode: bool, handle_set_bash_mode: BoolCallback, **props):
        border_color = Theme.DARK_PINK if bash_mode else Theme.DARK_GRAY
        super().__init__(border_color=Colors.HEX(border_color), bash_mode=bash_mode, handle_set_bash_mode=handle_set_bash_mode, **props)

    def handle_input(self, ch: str) -> None:
        if self.props['bash_mode'] and not self.state['content'] and ch == '\x7f':
            self.props['handle_set_bash_mode'](False)
        elif not self.state['content'] and ch == '!':
            self.props['handle_set_bash_mode'](True)
        else:
            super().handle_input(ch)

    @property
    def content_width(self) -> int:
        return max(0, self.box_width - 5)  # 2 spaces for borders, 3 spaces for prompt arrow

    def render_contents(self) -> str:
        marker = Colors.hex('!', Theme.PINK) if self.props['bash_mode'] else '>'
        lines = super().render_contents().split('\n')
        lines = [f" {marker} {line}" if i == 0 else f"   {line}" for i, line in enumerate(lines)]
        return '\n'.join(lines)
