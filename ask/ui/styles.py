import os
import re
from collections import deque
from dataclasses import dataclass
from enum import Enum
from functools import partial

ANSI_BACKGROUND_OFFSET = 10
ANSI_256_SUPPORT = '256color' in os.getenv("TERM", '')
ANSI_16M_SUPPORT = 'truecolor' in os.getenv("COLORTERM", '') or '24bit' in os.getenv("COLORTERM", '')

def ansi16(code: int, *, offset: int = 0) -> str:
    return f"\u001B[{code + offset}m"

def ansi256(code: int, *, offset: int = 0) -> str:
    return f"\u001B[{38 + offset};5;{code}m"

def ansi16m(red: int, green: int, blue: int, *, offset: int = 0) -> str:
    return f"\u001B[{38 + offset};2;{red};{green};{blue}m"

def rgb_to_ansi256(red: int, green: int, blue: int) -> int:
    # From https://github.com/Qix-/color-convert/blob/3f0e0d4e92e235796ccb17f6e85c72094a651f49/conversions.js
    # We use the extended greyscale palette here, with the exception of
    # black and white. normal palette only has 4 greyscale shades.
    if red == green and green == blue:
        if red < 8:
            return 16
        if red > 248:
            return 231
        return round(((red - 8) / 247) * 24) + 232

    return 16 + (36 * round(red / 255 * 5)) + (6 * round(green / 255 * 5)) + round(blue / 255 * 5)

def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    matches = re.search(r'[a-f\d]{6}|[a-f\d]{3}', str(hex_str), re.IGNORECASE)
    if not matches:
        return (0, 0, 0)

    color_string = matches.group(0)
    if len(color_string) == 3:
        color_string = ''.join([c + c for c in color_string])

    integer = int(color_string, 16)
    return (integer >> 16) & 0xFF, (integer >> 8) & 0xFF, integer & 0xFF

def hex_to_ansi256(hex_str: str) -> int:
    rgb = hex_to_rgb(hex_str)
    return rgb_to_ansi256(rgb[0], rgb[1], rgb[2])

def ansi256_to_ansi(code: int) -> int:
    if code < 8:
        return 30 + code
    if code < 16:
        return 90 + (code - 8)

    if code >= 232:
        red = (((code - 232) * 10) + 8) / 255
        green = red
        blue = red
    else:
        code -= 16
        remainder = code % 36
        red = (code // 36) / 5
        green = (remainder // 6) / 5
        blue = (remainder % 6) / 5

    value = max(red, green, blue) * 2
    if value == 0:
        return 30

    result = 30 + ((round(blue) << 2) | (round(green) << 1) | round(red))
    if value == 2:
        result += 60

    return result

def rgb_to_ansi(red: int, green: int, blue: int) -> int:
    return ansi256_to_ansi(rgb_to_ansi256(red, green, blue))

def hex_to_ansi(hex_str: str) -> int:
    return ansi256_to_ansi(hex_to_ansi256(hex_str))

def rgb_to_best_ansi(red: int, green: int, blue: int, *, offset: int = 0) -> str:
    if ANSI_16M_SUPPORT:
        return ansi16m(red, green, blue, offset=offset)
    elif ANSI_256_SUPPORT:
        code = rgb_to_ansi256(red, green, blue)
        return ansi256(code, offset=offset)
    else:
        code = rgb_to_ansi(red, green, blue)
        return ansi16(code, offset=offset)

def hex_to_best_ansi(hex_str: str, *, offset: int = 0) -> str:
    return rgb_to_best_ansi(*hex_to_rgb(hex_str), offset=offset)

def apply_style(text: str, start: str, end: str) -> str:
    return f"{start}{text}{end}"

def ansi_len(text: str) -> int:
    return len(ansi_strip(text))

def ansi_strip(text: str) -> str:
    return re.sub(r'\u001B\[[0-9;]+m', '', text)

def ansi_slice(string: str, start: int, end: int) -> str:
    style_starts = {v: k for k, v in Styles.__dict__.items() if k.isupper() and not k.endswith('_END')}
    style_stops = {v: k.removesuffix('_END') for k, v in Styles.__dict__.items() if k.endswith('_END')}

    ansi_pattern = re.compile(r'\u001B\[([0-9;]+)m')
    chunks = []
    last_pos = 0

    for match in ansi_pattern.finditer(string):
        if match.start() > last_pos:
            chunks.append(string[last_pos:match.start()])
        chunks.append(match.group())
        last_pos = match.end()
    if last_pos < len(string):
        chunks.append(string[last_pos:])

    result = []
    current_pos = 0
    active_styles: set[str] = set()
    active_color = None
    active_bgcolor = None

    for chunk in chunks:
        if match_ := ansi_pattern.match(chunk):
            if current_pos >= start:
                result.append(chunk)
            codes = deque(match_.group(1).split(';'))
            while codes:
                code = int(codes.popleft())
                ansi_code = f'\u001B[{code}m'
                if code in (38, 48) and codes:
                    if codes[0] == '5' and len(codes) >= 2:
                        _, color_code = codes.popleft(), codes.popleft()
                        ansi_code = f'\u001B[{code};5;{color_code}m'
                    elif codes[0] == '2' and len(codes) >= 4:
                        _, r, g, b = codes.popleft(), codes.popleft(), codes.popleft(), codes.popleft()
                        ansi_code = f'\u001B[{code};2;{r};{g};{b}m'

                if code == 0:
                    active_styles.clear()
                    active_color = None
                    active_bgcolor = None
                elif code in range(30, 39) or code in range(90, 98):
                    active_color = ansi_code
                elif code in range(40, 49) or code in range(100, 108):
                    active_bgcolor = ansi_code
                elif code == 39:
                    active_color = None
                elif code == 49:
                    active_bgcolor = None
                elif ansi_code in style_starts:
                    active_styles.add(ansi_code)
                elif ansi_code in style_stops:
                    active_styles.discard(Styles.__dict__[style_stops[ansi_code]])

        else:
            chunk_end = current_pos + len(chunk)
            if chunk_end <= start:
                current_pos = chunk_end
                continue
            if current_pos >= end:
                break

            slice_start = max(0, start - current_pos)
            slice_end = min(len(chunk), end - current_pos)
            if slice_start < slice_end:
                if not result:
                    result.extend(active_styles)
                    if active_color:
                        result.append(active_color)
                    if active_bgcolor:
                        result.append(active_bgcolor)
                result.append(chunk[slice_start:slice_end])
            if chunk_end >= end:
                break

            current_pos = chunk_end

    reset = ''
    if active_color:
        reset += Colors.END
    if active_bgcolor:
        reset += Colors.BG_END
    if active_styles:
        reset += Styles.RESET
    return ''.join(result) + reset

def wrap_lines(content: str, max_width: int) -> str:
    lines = []
    pos = 0
    while line := ansi_slice(content, pos, pos + max_width):
        line_len = max_width
        if (newline_pos := line.find('\n')) >= 0:
            first_line = line[:newline_pos]
            first_line_len = ansi_len(first_line)
            line = ansi_slice(content, pos, pos + first_line_len)
            line_len = first_line_len + 1
        lines.append(line)
        pos += line_len
    return '\n'.join(lines)


class Styles:
    RESET = "\u001B[0m"
    BOLD = "\u001B[1m"
    ITALIC = "\u001B[3m"
    UNDERLINE = "\u001B[4m"
    OVERLINE = "\u001B[53m"
    INVERSE = "\u001B[7m"
    HIDDEN = "\u001B[8m"
    STRIKETHROUGH = "\u001B[9m"

    BOLD_END = "\u001B[22m"
    ITALIC_END = "\u001B[23m"
    UNDERLINE_END = "\u001B[24m"
    OVERLINE_END = "\u001B[55m"
    INVERSE_END = "\u001B[27m"
    HIDDEN_END = "\u001B[28m"
    STRIKETHROUGH_END = "\u001B[29m"

    bold = staticmethod(partial(apply_style, start=BOLD, end=BOLD_END))
    italic = staticmethod(partial(apply_style, start=ITALIC, end=ITALIC_END))
    underline = staticmethod(partial(apply_style, start=UNDERLINE, end=UNDERLINE_END))
    overline = staticmethod(partial(apply_style, start=OVERLINE, end=OVERLINE_END))
    inverse = staticmethod(partial(apply_style, start=INVERSE, end=INVERSE_END))
    hidden = staticmethod(partial(apply_style, start=HIDDEN, end=HIDDEN_END))
    strikethrough = staticmethod(partial(apply_style, start=STRIKETHROUGH, end=STRIKETHROUGH_END))


class Colors:
    BLACK = "\u001B[30m"
    RED = "\u001B[31m"
    GREEN = "\u001B[32m"
    YELLOW = "\u001B[33m"
    BLUE = "\u001B[34m"
    MAGENTA = "\u001B[35m"
    CYAN = "\u001B[36m"
    WHITE = "\u001B[37m"
    BLACK_BRIGHT = "\u001B[90m"
    RED_BRIGHT = "\u001B[91m"
    GREEN_BRIGHT = "\u001B[92m"
    YELLOW_BRIGHT = "\u001B[93m"
    BLUE_BRIGHT = "\u001B[94m"
    MAGENTA_BRIGHT = "\u001B[95m"
    CYAN_BRIGHT = "\u001B[96m"
    WHITE_BRIGHT = "\u001B[97m"
    END = "\u001B[39m"

    BG_BLACK = "\u001B[40m"
    BG_RED = "\u001B[41m"
    BG_GREEN = "\u001B[42m"
    BG_YELLOW = "\u001B[43m"
    BG_BLUE = "\u001B[44m"
    BG_MAGENTA = "\u001B[45m"
    BG_CYAN = "\u001B[46m"
    BG_WHITE = "\u001B[47m"
    BG_BLACK_BRIGHT = "\u001B[100m"
    BG_RED_BRIGHT = "\u001B[101m"
    BG_GREEN_BRIGHT = "\u001B[102m"
    BG_YELLOW_BRIGHT = "\u001B[103m"
    BG_BLUE_BRIGHT = "\u001B[104m"
    BG_MAGENTA_BRIGHT = "\u001B[105m"
    BG_CYAN_BRIGHT = "\u001B[106m"
    BG_WHITE_BRIGHT = "\u001B[107m"
    BG_END = "\u001B[49m"

    HEX = staticmethod(hex_to_best_ansi)
    RGB = staticmethod(rgb_to_best_ansi)
    BG_HEX = staticmethod(partial(hex_to_best_ansi, offset=ANSI_BACKGROUND_OFFSET))
    BG_RGB = staticmethod(partial(rgb_to_best_ansi, offset=ANSI_BACKGROUND_OFFSET))

    @staticmethod
    def ansi(text: str, code: str) -> str:
        return apply_style(text, start=code, end=Colors.END if code else '')
    @staticmethod
    def hex(text: str, hex: str) -> str:
        return apply_style(text, start=hex_to_best_ansi(hex), end=Colors.END)
    @staticmethod
    def rgb(text: str, rgb: tuple[int, int, int]) -> str:
        return apply_style(text, start=rgb_to_best_ansi(*rgb), end=Colors.END)

    @staticmethod
    def bg_ansi(text: str, code: str) -> str:
        return apply_style(text, start=code, end=Colors.BG_END if code else '')
    @staticmethod
    def bg_hex(text: str, hex: str) -> str:
        return apply_style(text, start=hex_to_best_ansi(hex, offset=ANSI_BACKGROUND_OFFSET), end=Colors.BG_END)
    @staticmethod
    def bg_rgb(text: str, rgb: tuple[int, int, int]) -> str:
        return apply_style(text, start=rgb_to_best_ansi(*rgb, offset=ANSI_BACKGROUND_OFFSET), end=Colors.BG_END)



class Flex(Enum):
    VERTICAL = 'vertical'
    HORIZONTAL = 'horizontal'

@dataclass
class BorderStyle:
    top_left: str
    top: str
    top_right: str
    right: str
    bottom_right: str
    bottom: str
    bottom_left: str
    left: str

class Borders:
    SINGLE = BorderStyle("┌", "─", "┐", "│", "┘", "─", "└", "│")
    DOUBLE = BorderStyle("╔", "═", "╗", "║", "╝", "═", "╚", "║")
    ROUND = BorderStyle("╭", "─", "╮", "│", "╯", "─", "╰", "│")
    BOLD = BorderStyle("┏", "━", "┓", "┃", "┛", "━", "┗", "┃")
    SINGLE_DOUBLE = BorderStyle("╓", "─", "╖", "║", "╜", "─", "╙", "║")
    DOUBLE_SINGLE = BorderStyle("╒", "═", "╕", "│", "╛", "═", "╘", "│")
    CLASSIC = BorderStyle("+", "-", "+", "|", "+", "-", "+", "|")

class Theme:
    RED = '#FF6B80'
    DARK_RED = '#7A2936'
    FADED_RED = '#69484D'
    LIGHT_ORANGE = '#EB9F7F'
    ORANGE = '#D77757'
    GREEN = '#4EBA65'
    DARK_GREEN = '#225C2B'
    FADED_GREEN = '#47584A'
    BLUE = '#B1B9F9'
    PINK = '#FD5DB1'
    GRAY = '#AAAAAA'
    DARK_GRAY = '#888888'
    WHITE = '#FFFFFF'
