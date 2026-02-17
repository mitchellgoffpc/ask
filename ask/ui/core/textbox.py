from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import partial

from ask.ui.core.components import BaseController, Component, Length, Text, Widget
from ask.ui.core.styles import Axis, Color, Colors, Styles, Wrap

REMOVE_CONTROL_CHARS = dict.fromkeys(range(32)) | {0xa: 0xa, 0xd: 0xa}

def is_stop_char(ch: str) -> bool:
    return ch in ' \t\n<>@/|&;(){}[]"\'`'

# TODO: Feels silly to have two different wrap_lines implementations, can we replace this one with the 'real' one in styles.py?
def wrap_lines(text: str, width: int, wrap: Wrap) -> Iterator[tuple[str, bool]]:
    if width <= 0:
        return

    pos = 0
    newline_pos = -1
    while pos < len(text):
        newline_pos = text.find('\n', pos)
        if newline_pos != -1 and newline_pos - pos <= width:
            yield text[pos:newline_pos], True
            pos = newline_pos + 1
        elif newline_pos == -1 and len(text) - pos <= width:
            yield text[pos:], False
            break
        else:
            segment_end = pos + width
            if wrap is not Wrap.EXACT:
                yield text[pos:segment_end], False
                pos = segment_end
            else:
                space_pos = text.rfind(' ', pos, segment_end + 1)
                if space_pos > pos:
                    yield text[pos:space_pos + 1], False
                    pos = space_pos + 1
                else:
                    yield text[pos:segment_end], False
                    pos = segment_end
    if newline_pos != -1:
        yield '', False


@dataclass
class TextBox(Widget):
    width: Length = 1.0
    text: str | None = None
    placeholder: str = ""
    wrap: Wrap = Wrap.WORDS
    color: Color | None = None
    placeholder_color: Color | None = None
    highlight_color: Color | None = None
    history: list[str] | None = None
    handle_input: Callable[[str, int], bool] | None = None
    handle_page: Callable[[int], None] | None = None
    handle_change: Callable[[str], None] | None = None
    handle_submit: Callable[[str], bool] | None = None

class TextBoxController(BaseController[TextBox]):
    state = ['_text', '_cursor_pos', 'history', 'history_idx', 'mark']
    _text = ''
    _cursor_pos = 0
    kill_buffer = ''
    mark: int | None = None

    def __init__(self, props: TextBox) -> None:
        super().__init__(props)
        self.history = (props.history or []) + [props.text or '']
        self.history_idx = len(self.history) - 1
        self.undo_stack: deque[tuple[str, int]] = deque(maxlen=1000)

    @property
    def content_width(self) -> int:
        if self.tree and self.text_ref.uuid in self.tree.widths:
            return max(0, self.tree.widths[self.text_ref.uuid] - self.text_ref.chrome(Axis.HORIZONTAL))
        return 0

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, text: str) -> None:
        self._text = text
        if self.props.handle_change:
            self.props.handle_change(text)
        self.history = [*self.history[:self.history_idx], text, *self.history[self.history_idx + 1:]]

    @property
    def cursor_pos(self) -> int:
        return min(self._cursor_pos, len(self.text))

    @cursor_pos.setter
    def cursor_pos(self, pos: int) -> None:
        self._cursor_pos = pos

    def handle_update(self, new_props: TextBox) -> None:
        if new_props.text is not None and new_props.text != self._text:
            self._text = new_props.text
            self._cursor_pos = len(new_props.text)
        if new_props.history is not None and new_props.history != self.props.history:
            self.history = [*(new_props.history or []), new_props.text if new_props.text is not None else self._text]
            self.history_idx = len(self.history) - 1
        super().handle_update(new_props)

    def handle_input(self, ch: str) -> None:
        if self.props.handle_input and not self.props.handle_input(ch, self.cursor_pos):
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
            elif direction == '5~':  # Page down
                text, cursor_pos, history_idx = self.change_history_idx(1)
            elif direction == '6~':  # Page up
                text, cursor_pos, history_idx = self.change_history_idx(-1)
        elif ch == '\x7f' and cursor_pos > 0:  # Alt+Backspace, delete word
            pos = cursor_pos - 1
            while pos >= 0 and is_stop_char(text[pos]):
                pos -= 1
            while pos >= 0 and not is_stop_char(text[pos]):
                pos -= 1
            text = text[:pos + 1] + text[cursor_pos:]
            cursor_pos = pos + 1
        elif ch == 'd':  # Alt+D, delete word
            pos = cursor_pos
            while pos < len(text) and is_stop_char(text[pos]):
                pos += 1
            while pos < len(text) and not is_stop_char(text[pos]):
                pos += 1
            text = text[:cursor_pos] + text[pos:]
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
        total_lines = self.get_total_lines()
        if ((direction < 0 and current_line == 0) or
            (direction > 0 and current_line == total_lines - 1)):
            return self.change_history_idx(direction)

        new_line = max(0, min(total_lines - 1, current_line + direction))
        if new_line != current_line:
            line_start, line_end = self.get_visual_line_bounds(new_line)
            cursor_pos = min(line_start + current_col, line_end)
            return self.text, cursor_pos, self.history_idx
        return self.text, self.cursor_pos, self.history_idx

    def get_cursor_line_col(self) -> tuple[int, int]:
        text_before_cursor = self.text[:self.cursor_pos]
        lines = list(wrap_lines(text_before_cursor, self.content_width, self.props.wrap))
        if not lines:
            return 0, 0
        return len(lines) - 1, len(lines[-1][0])

    def get_total_lines(self) -> int:
        return sum(1 for _ in wrap_lines(self.text, self.content_width, self.props.wrap))

    def get_visual_line_bounds(self, line: int) -> tuple[int, int]:
        position = 0
        for i, (line_content, is_hard) in enumerate(wrap_lines(self.text, self.content_width, self.props.wrap)):
            if i == line:
                return position, position + len(line_content)
            position += len(line_content)
            if is_hard:
                position += 1
        return len(self.text), len(self.text)

    def contents(self) -> list[Component | None]:
        if not self.text and self.props.placeholder:
            color_fn = partial(Colors.apply, color=self.props.placeholder_color) if self.props.placeholder_color else Styles.dim
            styled_text = Styles.inverse(self.props.placeholder[0]) + color_fn(self.props.placeholder[1:])
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
                    region = Colors.apply_bg(text[start:end], self.props.highlight_color) + Styles.inverse(under)
                else:
                    region = Styles.inverse(under) + Colors.apply_bg(text[start+1:end], self.props.highlight_color)
                styled_text = Colors.apply(before + region + after, self.props.color)
            else:
                before = text[:cursor_pos]
                after = text[cursor_pos + 1:]
                under = text[cursor_pos:cursor_pos + 1] if cursor_pos < len(text) else ' '
                styled_text = Colors.apply(before + Styles.inverse(under) + after, self.props.color)

        self.text_ref = Text(styled_text, width=self.props.width, wrap=Wrap.EXACT if self.props.wrap is Wrap.EXACT else Wrap.WORDS_WITH_CURSOR)
        return [self.text_ref]
