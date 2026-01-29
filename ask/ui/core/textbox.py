from collections import deque
from dataclasses import dataclass
from typing import Callable, ClassVar

from ask.ui.core.components import Length, Component, Controller, Text, Widget
from ask.ui.core.styles import Axis, Colors, Styles

REMOVE_CONTROL_CHARS = dict.fromkeys(range(0, 32)) | {0xa: 0xa, 0xd: 0xa}

def is_stop_char(ch: str) -> bool:
    return ch in ' \t\n<>@/|&;(){}[]"\'`'

@dataclass
class TextBox(Widget):
    __controller__: ClassVar = lambda _: TextBoxController
    width: Length = 1.0
    text: str | None = None
    placeholder: str = ""
    history: list[str] | None = None
    handle_input: Callable[[str, int], bool] | None = None
    handle_page: Callable[[int], None] | None = None
    handle_change: Callable[[str], None] | None = None
    handle_submit: Callable[[str], bool] | None = None


class TextBoxController(Controller[TextBox]):
    state = ['text', 'cursor_pos', 'history', 'history_idx', 'mark']
    _text = ''
    _cursor_pos = 0
    kill_buffer = ''
    mark: int | None = None

    def __init__(self, props: TextBox):
        super().__init__(props)
        self.history = (props.history or []) + [props.text or '']
        self.history_idx = len(self.history) - 1
        self.undo_stack: deque[tuple[str, int]] = deque(maxlen=1000)

    def __call__(self, new_props: TextBox) -> None:
        if new_props.text is not None and new_props.text != self._text:
            self._text = new_props.text
            self._cursor_pos = len(new_props.text)
        if new_props.history is not None and new_props.history != self.props.history:
            self.history = [*(new_props.history or []), new_props.text if new_props.text is not None else self._text]
            self.history_idx = len(self.history) - 1
        super().__call__(new_props)

    @property
    def content_width(self) -> int:
        if self.tree and self.text_ref.uuid in self.tree.widths:
            return max(0, self.tree.widths[self.text_ref.uuid] - self.text_ref.chrome(Axis.HORIZONTAL))
        raise ValueError("TextBoxController: content_width requested before layout")

    @property
    def cursor_pos(self) -> int:
        return min(self._cursor_pos, len(self.text))

    @property
    def text(self) -> str:
        return self.props.text if self.props.text is not None else self._text

    @text.setter
    def text(self, text: str) -> None:
        self._text = text
        if self.props.handle_change:
            self.props.handle_change(text)
        self.history = [*self.history[:self.history_idx], text, *self.history[self.history_idx + 1:]]

    def handle_input(self, ch: str) -> None:
        if self.props.handle_input:
            if not self.props.handle_input(ch, self.cursor_pos):
                return

        text = self.text
        cursor_pos = self.cursor_pos
        history_idx = self.history_idx

        if ch == '\r':  # Enter, submit
            if self.props.handle_submit and self.props.handle_submit(text):
                self.undo_stack.clear()
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
        elif ch == '\x07':  # Ctrl+G - unset mark
            self.mark = None
        elif ch == '\x0b':  # Ctrl+K - kill to next newline
            next_newline = text.find('\n', cursor_pos)
            if next_newline == -1:
                self.kill_buffer = text[cursor_pos:]
                text = text[:cursor_pos]
            else:
                self.kill_buffer = text[cursor_pos:next_newline]
                text = text[:cursor_pos] + text[next_newline:]
        elif ch == '\x0e':  # Ctrl+N - move to next line
            text, cursor_pos, history_idx = self.change_line(1)
        elif ch == '\x0f':  # Ctrl+O - insert newline after cursor
            text = text[:cursor_pos] + '\n' + text[cursor_pos:]
        elif ch == '\x10':  # Ctrl+P - move to previous line
            text, cursor_pos, history_idx = self.change_line(-1)
        elif ch == '\x14':  # Ctrl+T - transpose characters
            if cursor_pos > 0 and cursor_pos < len(text):
                text = text[:cursor_pos - 1] + text[cursor_pos] + text[cursor_pos - 1] + text[cursor_pos + 1:]
                cursor_pos += 1
        elif ch == '\x17':  # Ctrl+W - kill region
            if self.mark is not None:
                start, end = min(self.mark, cursor_pos), max(self.mark, cursor_pos)
                self.kill_buffer = text[start:end]
                self.mark = None
                text = text[:start] + text[end:]
                cursor_pos = start
        elif ch == '\x19':  # Ctrl+Y - yank
            if self.kill_buffer:
                text = text[:cursor_pos] + self.kill_buffer + text[cursor_pos:]
                cursor_pos += len(self.kill_buffer)
        elif ch == '\x1f':  # Ctrl+/ - undo
            if self.undo_stack:
                text, cursor_pos = self.undo_stack.pop()
                self._cursor_pos = cursor_pos
                if text != self.text:
                    self.text = text
                return
        elif ch == '\x00':  # Ctrl+Space - set mark
            self.mark = cursor_pos
        elif ch.startswith('\x1b'):  # Escape sequence
            text, cursor_pos, history_idx = self.handle_escape_input(ch[1:])
        else:  # Regular character(s)
            ch = ch.translate(REMOVE_CONTROL_CHARS)
            text = text[:cursor_pos] + ch + text[cursor_pos:]
            cursor_pos += len(ch)

        # Yes, it does need to be done in this particular order
        if text != self.text:
            self.undo_stack.append((self.text, self.cursor_pos))
        self._cursor_pos = cursor_pos
        self.history_idx = history_idx
        if text != self.text:
            self.text = text

    def handle_escape_input(self, ch: str) -> tuple[str, int, int]:
        text = self.text
        cursor_pos = self.cursor_pos
        history_idx = self.history_idx

        if ch.startswith('['):  # Arrow keys and other sequences
            direction = ch[1:]
            if direction == 'D' and cursor_pos > 0:  # Left arrow
                cursor_pos -= 1
            elif direction == 'C' and cursor_pos < len(text):  # Right arrow
                cursor_pos += 1
            elif direction == 'A':  # Up arrow
                text, cursor_pos, history_idx = self.change_line(-1)
            elif direction == 'B':  # Down arrow
                text, cursor_pos, history_idx = self.change_line(1)
            elif direction == '5~':  # Page Down
                text, cursor_pos, history_idx = self.change_history_idx(-1)
            elif direction == '6~':  # Page Up
                text, cursor_pos, history_idx = self.change_history_idx(1)
        elif ch == '\x7f' and cursor_pos > 0:  # Alt+Backspace, delete word
            pos = cursor_pos - 1
            while pos >= 0 and is_stop_char(text[pos]):
                pos -= 1
            while pos >= 0 and not is_stop_char(text[pos]):
                pos -= 1
            text = text[:pos + 1] + text[cursor_pos:]
            cursor_pos = pos + 1
        elif ch == '\r':  # Alt+Enter, newline
            text = text[:cursor_pos] + '\n' + text[cursor_pos:]
            cursor_pos += 1
        elif ch == 'f':  # Alt+F, move forward one word
            pos = cursor_pos
            while pos < len(text) and not is_stop_char(text[pos]):
                pos += 1
            while pos < len(text) and is_stop_char(text[pos]):
                pos += 1
            cursor_pos = pos
        elif ch == 'b':  # Alt+B, move backward one word
            pos = cursor_pos - 1
            while pos >= 0 and is_stop_char(text[pos]):
                pos -= 1
            while pos >= 0 and not is_stop_char(text[pos]):
                pos -= 1
            cursor_pos = pos + 1

        return text, cursor_pos, history_idx

    def change_history_idx(self, direction: int) -> tuple[str, int, int]:
        history = self.history
        history_idx = self.history_idx
        new_history_idx = max(0, min(len(history) - 1, history_idx + direction))
        if new_history_idx != history_idx:
            if self.props.handle_page:
                self.props.handle_page(new_history_idx)
            history_idx = new_history_idx
            cursor_pos = len(history[new_history_idx])
            text = history[new_history_idx]
            return text, cursor_pos, history_idx
        return self.text, self.cursor_pos, history_idx

    def change_line(self, direction: int) -> tuple[str, int, int]:
        current_line, current_col = self.get_cursor_line_col()
        if ((direction < 0 and current_line == 0) or
            (direction > 0 and current_line == self.get_total_lines() - 1)):
            return self.change_history_idx(direction)

        new_line = max(0, min(self.get_total_lines() - 1, current_line + direction))
        if new_line != current_line:
            line_start = self.get_line_start_position(new_line)
            cursor_pos = min(line_start + current_col, self.get_line_end_position(new_line))
            return self.text, cursor_pos, self.history_idx
        return self.text, self.cursor_pos, self.history_idx

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

    def contents(self) -> list[Component | None]:
        if not self.text and self.props.placeholder:
            styled_text = Styles.inverse(self.props.placeholder[0]) + Colors.hex(self.props.placeholder[1:], '#999999')
        else:
            cursor_pos = self.cursor_pos + self.text.count('\n', 0, self.cursor_pos)
            text = self.text.replace('\n', ' \n')
            if text[cursor_pos:cursor_pos + 1] == '\n':
                cursor_pos -= 1

            if self.mark is not None:
                mark_pos = self.mark + self.text.count('\n', 0, self.mark)
                start, end = min(mark_pos, cursor_pos), max(mark_pos, cursor_pos)
                before = text[:start]
                after = text[end + 1:]
                under = text[cursor_pos:cursor_pos + 1] if cursor_pos < len(text) else ' '
                if cursor_pos == end:
                    region = Colors.bg_hex(text[start:end], '#333333') + Styles.inverse(under)
                else:
                    region = Styles.inverse(under) + Colors.bg_hex(text[start+1:end], '#333333')
                styled_text = before + region + after
            else:
                before = text[:cursor_pos]
                after = text[cursor_pos + 1:]
                under = text[cursor_pos:cursor_pos + 1] if cursor_pos < len(text) else ' '
                styled_text = before + Styles.inverse(under) + after

        self.text_ref = Text(styled_text, width=self.props.width)
        return [self.text_ref]
