from typing import Any, cast
from ask.ui.components import Box, Size, TextCallback, wrap_lines
from ask.ui.styles import Styles, Colors

class TextBox(Box):
    leaf = True
    initial_state = {'text': '', 'cursor_pos': 0}

    def __init__(
        self,
        width: Size = 1.0,
        text: str | None = None,
        placeholder: str = "",
        handle_submit: TextCallback | None = None,
        handle_change: TextCallback | None = None,
        history: list[str] | None = None,
        **props: Any
    ) -> None:
        super().__init__(width=width, text=text, handle_change=handle_change, handle_submit=handle_submit, placeholder=placeholder, history=history, **props)
        assert width is not None, "TextBox width must be specified"
        self.state['history'] = [*(history or []), text or '']
        self.state['history_index'] = len(self.state['history']) - 1

    @property
    def content_width(self) -> int:
        return self.get_content_width(self.rendered_width)

    @property
    def cursor_pos(self) -> int:
        return min(cast(int, self.state['cursor_pos']), len(self.text))

    @property
    def text(self) -> str:
        return cast(str, self.props['text'] if self.props['text'] is not None else self.state['text'])

    @text.setter
    def text(self, text: str) -> None:
        if self.props['text'] is None:
            self.state['text'] = text
        elif self.props['handle_change'] is not None:
            self.props['handle_change'](text)
        history = self.state['history']
        history_index = self.state['history_index']
        self.state['history'] = [*history[:history_index], text, *history[history_index + 1:]]

    def handle_update(self, new_props: dict[str, Any]) -> None:
        if 'history' in new_props and new_props['history'] != self.props['history']:
            self.state['history'] = [*(new_props['history'] or []), new_props['text'] if new_props['text'] is not None else self.state['text']]
            self.state['history_index'] = len(self.state['history']) - 1

    def handle_input(self, ch: str) -> None:
        text = self.text
        cursor_pos = self.cursor_pos

        if ch == '\r':  # Enter, submit
            if self.props['handle_submit']:
                self.props['handle_submit'](text)
        elif ch == '\x7f':  # Backspace
            if cursor_pos > 0:
                text = text[:cursor_pos - 1] + text[cursor_pos:]
                cursor_pos -= 1
        elif ch == '\x01':  # Ctrl+A - move to start of paragraph
            cursor_pos = text.rfind('\n', 0, cursor_pos) + 1
        elif ch == '\x02':  # Ctrl+B - move backward one character
            if cursor_pos > 0:
                cursor_pos -= 1
        elif ch == '\x03':  # Ctrl+C - break
            pass  # Handled by terminal
        elif ch == '\x04':  # Ctrl+D - delete character
            if text and cursor_pos < len(text):
                text = text[:cursor_pos] + text[cursor_pos + 1:]
        elif ch == '\x05':  # Ctrl+E - move to end of paragraph
            next_newline = text.find('\n', cursor_pos)
            cursor_pos = next_newline if next_newline != -1 else len(text)
        elif ch == '\x06':  # Ctrl+F - move forward one character
            if cursor_pos < len(text):
                cursor_pos += 1
        elif ch == '\x0b':  # Ctrl+K - kill to next newline
            next_newline = text.find('\n', cursor_pos)
            text = text[:cursor_pos] if next_newline == -1 else text[:cursor_pos] + text[next_newline:]
        elif ch == '\x0e':  # Ctrl+N - move to next line
            cursor_pos = self.get_next_line_position()
        elif ch == '\x0f':  # Ctrl+O - insert newline after cursor
            text = text[:cursor_pos] + '\n' + text[cursor_pos:]
        elif ch == '\x10':  # Ctrl+P - move to previous line
            cursor_pos = self.get_previous_line_position()
        elif ch == '\x14':  # Ctrl+T - transpose characters
            if cursor_pos > 0 and cursor_pos < len(text):
                text = text[:cursor_pos - 1] + text[cursor_pos] + text[cursor_pos - 1] + text[cursor_pos + 1:]
                cursor_pos += 1
        elif ch == '\x19':  # Ctrl+Y - yank
            pass  # TODO: Implement this
        elif ch.startswith('\x1b'):  # Escape sequence
            text, cursor_pos = self.handle_escape_input(ch[1:])
        else:  # Regular character(s)
            text = text[:cursor_pos] + ch + text[cursor_pos:]
            cursor_pos += len(ch)

        self.state['cursor_pos'] = cursor_pos
        if text != self.text:
            self.text = text

    def handle_escape_input(self, ch: str) -> tuple[str, int]:
        text = self.text
        cursor_pos = self.cursor_pos
        history = self.state['history']
        history_index = self.state['history_index']

        if ch.startswith('['):  # Arrow keys and other sequences
            direction = ch[1:]
            if direction == 'D' and cursor_pos > 0:  # Left arrow
                cursor_pos -= 1
            elif direction == 'C' and cursor_pos < len(text):  # Right arrow
                cursor_pos += 1
            elif direction == 'A':  # Up arrow
                cursor_pos = self.get_previous_line_position()
            elif direction == 'B':  # Down arrow
                cursor_pos = self.get_next_line_position()
                self.state['cursor_pos'] = cursor_pos
            elif direction == '5~' and history_index > 0:  # Page Down
                self.state['history_index'] = history_index - 1
                cursor_pos = len(history[history_index - 1])
                text = history[history_index - 1]
            elif direction == '6~' and history_index < len(history) - 1:  # Page Up
                self.state['history_index'] = history_index + 1
                cursor_pos = len(history[history_index + 1])
                text = history[history_index + 1]
        elif ch == '\x7f' and cursor_pos > 0:  # Alt+Backspace, delete word
            pos = cursor_pos - 1
            while pos >= 0 and text[pos].isspace():
                pos -= 1
            while pos >= 0 and not text[pos].isspace():
                pos -= 1
            text = text[:pos + 1] + text[cursor_pos:]
            cursor_pos = pos + 1
        elif ch == '\r':  # Alt+Enter, newline
            text = text[:cursor_pos] + '\n' + text[cursor_pos:]
            cursor_pos += 1
        elif ch == 'f':  # Alt+F, move forward one word
            pos = cursor_pos
            while pos < len(text) and not text[pos].isspace():
                pos += 1
            while pos < len(text) and text[pos].isspace():
                pos += 1
            cursor_pos = pos
        elif ch == 'b':  # Alt+B, move backward one word
            pos = cursor_pos - 1
            while pos >= 0 and text[pos].isspace():
                pos -= 1
            while pos >= 0 and not text[pos].isspace():
                pos -= 1
            cursor_pos = pos + 1

        return text, cursor_pos

    def get_previous_line_position(self):
        current_line, current_col = self.get_cursor_line_col()
        if current_line > 0:
            line_start = self.get_line_start_position(current_line - 1)
            return min(line_start + current_col, self.get_line_end_position(current_line - 1))
        return self.cursor_pos

    def get_next_line_position(self):
        current_line, current_col = self.get_cursor_line_col()
        if current_line < self.get_total_lines() - 1:
            line_start = self.get_line_start_position(current_line + 1)
            return min(line_start + current_col, self.get_line_end_position(current_line + 1))
        return self.cursor_pos

    def get_cursor_line_col(self) -> tuple[int, int]:
        paragraphs = self.text[:self.cursor_pos].split('\n')
        line = sum(max(1, (len(paragraph) + self.content_width) // self.content_width) for paragraph in paragraphs[:-1])
        line += len(paragraphs[-1]) // self.content_width
        col = len(paragraphs[-1]) % self.content_width
        return line, col

    def get_total_lines(self) -> int:
        return sum(max(1, (len(paragraph) + self.content_width) // self.content_width) for paragraph in self.text.split('\n'))

    def get_line_start_position(self, line: int) -> int:
        current_line = 0
        position = 0

        for paragraph in self.text.split('\n'):
            lines_in_paragraph = max(1, (len(paragraph) + self.content_width) // self.content_width)
            if current_line + lines_in_paragraph > line:
                return position + (line - current_line) * self.content_width
            current_line += lines_in_paragraph
            position += len(paragraph) + 1  # +1 for the newline

        return position

    def get_line_end_position(self, line: int) -> int:
        current_line = 0
        position = 0

        for paragraph in self.text.split('\n'):
            lines_in_paragraph = max(1, (len(paragraph) + self.content_width) // self.content_width)
            if current_line + lines_in_paragraph > line:  # Found the paragraph containing our target line
                relative_line = line - current_line
                end = min((relative_line + 1) * self.content_width, len(paragraph))
                return position + end
            current_line += lines_in_paragraph
            position += len(paragraph) + 1  # +1 for the newline

        return position

    def render_text(self) -> str:
        if not self.text and self.props['placeholder']:
            return Styles.inverse(self.props['placeholder'][0]) + Colors.hex(self.props['placeholder'][1:], '#999999')

        cursor_pos = self.cursor_pos + self.text.count('\n', 0, self.cursor_pos)
        text = self.text.replace('\n', ' \n')
        if text[cursor_pos:cursor_pos + 1] == '\n':
            cursor_pos -= 1
        before = text[:cursor_pos]
        after = text[cursor_pos + 1:]
        under = text[cursor_pos:cursor_pos + 1] if cursor_pos < len(text) else ' '
        return before + Styles.inverse(under) + after

    def render(self, _: list[str], max_width: int) -> str:
        return super().render([wrap_lines(self.render_text(), self.get_content_width(max_width))], max_width)
