from typing import Callable, Any
from ask.ui.components import Box, Size
from ask.ui.styles import Styles, Colors

TextCallback = Callable[[str], None]

class TextBox(Box):
    leaf = True
    initial_state = {'content': '', 'cursor_pos': 0}

    def __init__(
        self,
        width: Size = 1.0,
        handle_change: TextCallback | None = None,
        handle_submit: TextCallback | None = None,
        placeholder: str = "",
        **props: Any
    ) -> None:
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

    def render_contents(self) -> str:
        if not self.state['content'] and self.props['placeholder']:
            return Styles.inverse(self.props['placeholder'][0]) + Colors.hex(self.props['placeholder'][1:], '#999999')

        content: str = self.state['content']
        cursor_pos = self.state['cursor_pos']
        before = content[:cursor_pos]
        under = content[cursor_pos:cursor_pos + 1] if cursor_pos < len(content) else ' '
        after = content[cursor_pos + 1:]
        trailing_space = ' ' if after else ''
        return before + Styles.inverse(under) + after + trailing_space

    def render(self, _: list[str]) -> str:
        return super().render([self.render_contents()])
