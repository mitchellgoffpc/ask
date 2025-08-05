from typing import Any, Callable, cast
from ask.ui.components import Box, Size, TextCallback, wrap_lines
from ask.ui.styles import Styles, Colors

InputCallback = Callable[[str], bool]

class TextBox(Box):
    leaf = True
    initial_state = {'text': '', 'cursor_pos': 0}

    def __init__(
        self,
        width: Size = 1.0,
        text: str | None = None,
        placeholder: str = "",
        handle_input: InputCallback | None = None,
        handle_submit: TextCallback | None = None,
        handle_change: TextCallback | None = None,
        history: list[str] | None = None,
        **props: Any
    ) -> None:
        super().__init__(width=width, text=text, placeholder=placeholder, history=history,
                         handle_input=handle_input, handle_change=handle_change, handle_submit=handle_submit, **props)
        assert width is not None, "TextBox width must be specified"
        self.state['history'] = [*(history or []), text or '']
        self.state['history_idx'] = len(self.state['history']) - 1

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
        if self.props['handle_change'] is not None:
            self.props['handle_change'](text)
        history = self.state['history']
        history_idx = self.state['history_idx']
        self.state['history'] = [*history[:history_idx], text, *history[history_idx + 1:]]

    def handle_update(self, new_props: dict[str, Any]) -> None:
        if 'text' in new_props and len(new_props['text']) > len(self.props['text']):
            self.state['cursor_pos'] = len(new_props['text'])
        if 'history' in new_props and new_props['history'] != self.props['history']:
            self.state['history'] = [*(new_props['history'] or []), new_props['text'] if new_props['text'] is not None else self.state['text']]
            self.state['history_idx'] = len(self.state['history']) - 1

    def handle_raw_input(self, ch: str) -> None:
        if self.props.get('handle_input'):
            if not self.props['handle_input'](ch):
                return

        text = self.text
        cursor_pos = self.cursor_pos
        history_idx = self.state['history_idx']

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
            text, cursor_pos, history_idx = self.navigate_line(1)
        elif ch == '\x0f':  # Ctrl+O - insert newline after cursor
            text = text[:cursor_pos] + '\n' + text[cursor_pos:]
        elif ch == '\x10':  # Ctrl+P - move to previous line
            text, cursor_pos, history_idx = self.navigate_line(-1)
        elif ch == '\x14':  # Ctrl+T - transpose characters
            if cursor_pos > 0 and cursor_pos < len(text):
                text = text[:cursor_pos - 1] + text[cursor_pos] + text[cursor_pos - 1] + text[cursor_pos + 1:]
                cursor_pos += 1
        elif ch == '\x19':  # Ctrl+Y - yank
            pass  # TODO: Implement this
        elif ch.startswith('\x1b'):  # Escape sequence
            text, cursor_pos, history_idx = self.handle_escape_input(ch[1:])
        else:  # Regular character(s)
            text = text[:cursor_pos] + ch + text[cursor_pos:]
            cursor_pos += len(ch)

        self.state.update({'cursor_pos': cursor_pos, 'history_idx': history_idx})
        if text != self.text:
            self.text = text

    def handle_escape_input(self, ch: str) -> tuple[str, int, int]:
        text = self.text
        cursor_pos = self.cursor_pos
        history_idx = self.state['history_idx']

        if ch.startswith('['):  # Arrow keys and other sequences
            direction = ch[1:]
            if direction == 'D' and cursor_pos > 0:  # Left arrow
                cursor_pos -= 1
            elif direction == 'C' and cursor_pos < len(text):  # Right arrow
                cursor_pos += 1
            elif direction == 'A':  # Up arrow
                text, cursor_pos, history_idx = self.navigate_line(-1)
            elif direction == 'B':  # Down arrow
                text, cursor_pos, history_idx = self.navigate_line(1)
            elif direction == '5~':  # Page Down
                text, cursor_pos, history_idx = self.navigate_history(-1)
            elif direction == '6~':  # Page Up
                text, cursor_pos, history_idx = self.navigate_history(1)
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

        return text, cursor_pos, history_idx

    def navigate_history(self, direction: int) -> tuple[str, int, int]:
        history = self.state['history']
        history_idx = self.state['history_idx']
        new_history_idx = max(0, min(len(history) - 1, history_idx + direction))
        if new_history_idx != history_idx:
            history_idx = new_history_idx
            cursor_pos = len(history[new_history_idx])
            text = history[new_history_idx]
            return text, cursor_pos, history_idx
        return self.text, self.cursor_pos, history_idx

    def navigate_line(self, direction: int) -> tuple[str, int, int]:
        current_line, current_col = self.get_cursor_line_col()
        if ((direction < 0 and current_line == 0) or
            (direction > 0 and current_line == self.get_total_lines() - 1)):
            return self.navigate_history(direction)

        new_line = max(0, min(self.get_total_lines() - 1, current_line + direction))
        if new_line != current_line:
            line_start = self.get_line_start_position(new_line)
            cursor_pos = min(line_start + current_col, self.get_line_end_position(new_line))
            return self.text, cursor_pos, self.state['history_idx']
        return self.text, self.cursor_pos, self.state['history_idx']

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
