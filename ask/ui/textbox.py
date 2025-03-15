from typing import Callable
from ask.ui.components import Box, Size
from ask.ui.styles import Styles, Colors, Theme

TextCallback = Callable[[str], None]
BoolCallback = Callable[[bool], None]

class TextBox(Box):
    leaf = True
    initial_state = {'content': '', 'cursor_pos': 0}

    def __init__(
        self,
        width: Size = 1.0,
        handle_change: TextCallback | None = None,
        handle_submit: TextCallback | None = None,
        placeholder: str = "",
        **props
    ):
        super().__init__(width=width, handle_change=handle_change, handle_submit=handle_submit, placeholder=placeholder, **props)
        assert self.content_width > 0, "TextBox width must be specified"

    def handle_input(self, ch: str) -> None:
        cursor_pos = self.state['cursor_pos']
        content = self.state['content']
        if ch == '\r':  # Enter, submit
            if self.props['handle_submit']:
                self.props['handle_submit'](content)
        elif ch == '\x7f':  # Backspace
            if cursor_pos > 0:
                content = content[:cursor_pos - 1] + content[cursor_pos:]
                cursor_pos -= 1
        elif ch == '\x01':  # Ctrl+A - move to beginning of line
            current_line, _ = self.get_cursor_line_col()
            cursor_pos = self.get_line_start_position(current_line)
        elif ch == '\x02':  # Ctrl+B - move backward one character
            if cursor_pos > 0:
                cursor_pos -= 1
        elif ch == '\x03':  # Ctrl+C - break
            pass  # Handled by terminal
        elif ch == '\x04':  # Ctrl+D - delete character
            if content and cursor_pos < len(content):
                content = content[:cursor_pos] + content[cursor_pos + 1:]
        elif ch == '\x05':  # Ctrl+E - move to end of line
            current_line, _ = self.get_cursor_line_col()
            cursor_pos = self.get_line_end_position(current_line)
        elif ch == '\x06':  # Ctrl+F - move forward one character
            if cursor_pos < len(content):
                cursor_pos += 1
        elif ch == '\x0b':  # Ctrl+K - kill to end of line
            current_line, _ = self.get_cursor_line_col()
            line_end = self.get_line_end_position(current_line)
            content = content[:cursor_pos] + content[line_end:]
        elif ch == '\x0e':  # Ctrl+N - move to next line
            current_line, current_col = self.get_cursor_line_col()
            if current_line < self.get_total_lines() - 1:
                line_start = self.get_line_start_position(current_line + 1)
                cursor_pos = min(line_start + current_col, self.get_line_end_position(current_line + 1))
        elif ch == '\x0f':  # Ctrl+O - insert newline after cursor
            content = content[:cursor_pos + 1] + '\n' + content[cursor_pos + 1:]
        elif ch == '\x10':  # Ctrl+P - move to previous line
            current_line, current_col = self.get_cursor_line_col()
            if current_line > 0:
                line_start = self.get_line_start_position(current_line - 1)
                cursor_pos = min(line_start + current_col, self.get_line_end_position(current_line - 1))
        elif ch == '\x14':  # Ctrl+T - transpose characters
            if cursor_pos > 0 and cursor_pos < len(content):
                content = content[:cursor_pos - 1] + content[cursor_pos] + content[cursor_pos - 1] + content[cursor_pos + 1:]
                cursor_pos += 1
        elif ch == '\x19':  # Ctrl+Y - yank
            pass  # TODO: Implement this
        elif ch.startswith('\x1b'):  # Escape sequence
            content, cursor_pos = self.handle_escape_input(ch[1:])
        else:  # Regular character
            content = content[:cursor_pos] + ch + content[cursor_pos:]
            cursor_pos += 1

        if self.props['handle_change'] and content != self.state['content']:
            self.props['handle_change'](content)
        self.state.update({'content': content, 'cursor_pos': cursor_pos})

    def handle_escape_input(self, ch: str) -> tuple[str, int]:
        cursor_pos = self.state['cursor_pos']
        content = self.state['content']

        if ch.startswith('['):  # Arrow keys
            direction = ch[1:]
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
        elif ch == '\x7f' and cursor_pos > 0:  # Alt+Backspace, delete word
            pos = cursor_pos - 1
            while pos >= 0 and content[pos].isspace():
                pos -= 1
            while pos >= 0 and not content[pos].isspace():
                pos -= 1
            content = content[:pos + 1] + content[cursor_pos:]
            cursor_pos = pos + 1
        elif ch == '\r':  # Alt+Enter, newline
            content = content[:cursor_pos] + '\n' + content[cursor_pos:]
            cursor_pos += 1
        elif ch == 'f':  # Alt+F, move forward one word
            pos = cursor_pos
            while pos < len(content) and not content[pos].isspace():
                pos += 1
            while pos < len(content) and content[pos].isspace():
                pos += 1
            cursor_pos = pos
        elif ch == 'b':  # Alt+B, move backward one word
            pos = cursor_pos - 1
            while pos >= 0 and content[pos].isspace():
                pos -= 1
            while pos >= 0 and not content[pos].isspace():
                pos -= 1
            cursor_pos = pos + 1

        return content, cursor_pos

    def get_cursor_line_col(self) -> tuple[int, int]:
        paragraphs = self.state['content'][:self.state['cursor_pos']].split('\n')
        line = sum(max(1, (len(paragraph) + self.content_width - 1) // self.content_width) for paragraph in paragraphs[:-1])
        line += len(paragraphs[-1]) // self.content_width
        col = len(paragraphs[-1]) % self.content_width
        return line, col

    def get_total_lines(self) -> int:
        paragraphs = self.state['content'].split('\n')
        return sum(max(1, (len(paragraph) + self.content_width - 1) // self.content_width) for paragraph in paragraphs)

    def get_line_start_position(self, line: int) -> int:
        paragraphs = self.state['content'].split('\n')
        current_line = 0
        position = 0

        for paragraph in paragraphs:
            lines_in_paragraph = max(1, (len(paragraph) + self.content_width - 1) // self.content_width)
            if current_line + lines_in_paragraph > line:
                return position + (line - current_line) * self.content_width
            current_line += lines_in_paragraph
            position += len(paragraph) + 1  # +1 for the newline

        return position

    def get_line_end_position(self, line: int) -> int:
        paragraphs = self.state['content'].split('\n')
        current_line = 0
        position = 0

        for paragraph in paragraphs:
            lines_in_paragraph = max(1, (len(paragraph) + self.content_width - 1) // self.content_width)
            if current_line + lines_in_paragraph > line:
                # Found the paragraph containing our target line
                relative_line = line - current_line
                end = min((relative_line + 1) * self.content_width, len(paragraph))
                return position + end
            current_line += lines_in_paragraph
            position += len(paragraph) + 1  # +1 for the newline

        return position

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
