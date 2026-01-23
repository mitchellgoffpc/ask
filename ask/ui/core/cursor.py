import atexit
import os
import platform
import sys
from typing import TextIO

ESC = '\u001B['
OSC = '\u001B]'
BEL = '\u0007'
SEP = ';'

is_terminal_app = os.environ.get('TERM_PROGRAM') == 'Apple_Terminal'
is_windows = platform.system() == 'win32'

cursor_left = f"{ESC}G"
cursor_save_position = '\u001B7' if is_terminal_app else f"{ESC}s"
cursor_restore_position = '\u001B8' if is_terminal_app else f"{ESC}u"
cursor_get_position = f"{ESC}6n"
cursor_next_line = f"{ESC}E"
cursor_prev_line = f"{ESC}F"
cursor_hide = f"{ESC}?25l"
cursor_show = f"{ESC}?25h"

erase_end_line = f"{ESC}K"
erase_start_line = f"{ESC}1K"
erase_line = f"{ESC}2K"
erase_down = f"{ESC}J"
erase_up = f"{ESC}1J"
erase_screen = f"{ESC}2J"
scroll_up = f"{ESC}S"
scroll_down = f"{ESC}T"

clear_screen = '\u001Bc'
clear_terminal = f"{erase_screen}{ESC}0f" if is_windows else f"{erase_screen}{ESC}3J{ESC}H"

enter_alternative_screen = f"{ESC}?1049h"
exit_alternative_screen = f"{ESC}?1049l"


# Show / hide cursor

def show_cursor(writable_stream: TextIO = sys.stderr) -> None:
    if not hasattr(writable_stream, 'isatty') or not writable_stream.isatty():
        return
    writable_stream.write(cursor_show)
    writable_stream.flush()

def hide_cursor(writable_stream: TextIO = sys.stderr) -> None:
    if not hasattr(writable_stream, 'isatty') or not writable_stream.isatty():
        return
    writable_stream.write(cursor_hide)
    writable_stream.flush()

def show_cursor_on_exit() -> None:
    sys.stderr.write(cursor_show)
    sys.stderr.flush()


# Move cursor

def cursor_to(x: int, y: int | None = None) -> str:
    if y is None:
        return f"{ESC}{x + 1}G"
    return f"{ESC}{y + 1}{SEP}{x + 1}H"

def cursor_move(x: int, y: int = 0) -> str:
    return_value = ''

    if x < 0:
        return_value += f"{ESC}{-x}D"
    elif x > 0:
        return_value += f"{ESC}{x}C"

    if y < 0:
        return_value += f"{ESC}{-y}A"
    elif y > 0:
        return_value += f"{ESC}{y}B"

    return return_value

def cursor_up(count: int = 1) -> str:
    return f"{ESC}{count}A"

def cursor_down(count: int = 1) -> str:
    return f"{ESC}{count}B"

def cursor_forward(count: int = 1) -> str:
    return f"{ESC}{count}C"

def cursor_backward(count: int = 1) -> str:
    return f"{ESC}{count}D"

def erase_lines(count: int) -> str:
    clear = ''
    for i in range(count):
        clear += erase_line + (cursor_up() if i < count - 1 else '')
    if count:
        clear += cursor_left
    return clear

def link(text: str, url: str) -> str:
    return f"{OSC}8{SEP}{SEP}{url}{BEL}{text}{OSC}8{SEP}{SEP}{BEL}"


atexit.register(show_cursor_on_exit)
