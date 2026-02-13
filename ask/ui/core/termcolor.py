import os
import re
import select
import sys
import termios
import time
import tty

OSC = "\u001B]"
BEL = "\u0007"
ST = "\u001B\\"

XTERM_16 = [
    (0, 0, 0),
    (128, 0, 0),
    (0, 128, 0),
    (128, 128, 0),
    (0, 0, 128),
    (128, 0, 128),
    (0, 128, 128),
    (192, 192, 192),
    (128, 128, 128),
    (255, 0, 0),
    (0, 255, 0),
    (255, 255, 0),
    (0, 0, 255),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 255),
]

def terminal_fg_color(timeout: float = 0.05) -> tuple[int, int, int] | None:
    if spec := _query_osc_color(10, timeout=timeout) or _colorfgbg()[0]:
        return _parse_color_spec(spec)
    return None

def terminal_bg_color(timeout: float = 0.05) -> tuple[int, int, int] | None:
    if spec := _query_osc_color(11, timeout=timeout) or _colorfgbg()[1]:
        return _parse_color_spec(spec)
    return None


# Helper functions

def _colorfgbg() -> tuple[str | None, str | None]:
    value = os.getenv("COLORFGBG", "").split(';')
    fg = value[0]
    bg = value[-1] if len(value) > 1 else None
    return fg or None, bg or None

def _query_osc_color(code: int, *, timeout: float) -> str | None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdout.write(f"{OSC}{code};?{BEL}")
        sys.stdout.flush()
        if not (response := _read_osc_response(fd, timeout)):
            return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    if match := re.search(r"\x1b\]" + str(code) + r";([^\x07\x1b]+)", response):
        return match.group(1)
    return None

def _read_osc_response(fd: int, timeout: float) -> str:
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        remaining = max(0.0, deadline - time.time())
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready or not (chunk := os.read(fd, 256)):
            break
        buf += chunk
        if BEL.encode() in buf or ST.encode() in buf:
            break
    return buf.decode(errors="ignore")

def _parse_color_spec(spec: str) -> tuple[int, int, int] | None:
    spec = spec.strip()
    if spec.startswith("rgb:"):
        parts = spec[4:].split("/")
        if len(parts) >= 3:
            r, g, b, *_ = parts
            return _hex_component(r), _hex_component(g), _hex_component(b)
        return None
    elif match := re.search(r"[a-fA-F0-9]{6}|[a-fA-F0-9]{3}", spec):
        value = match.group(0)
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        integer = int(value, 16)
        return (integer >> 16) & 0xFF, (integer >> 8) & 0xFF, integer & 0xFF
    elif spec.isdigit() and 0 <= int(spec) < len(XTERM_16):
        return XTERM_16[int(spec)]
    else:
        return None

def _hex_component(component: str) -> int:
    value = int(component, 16)
    max_value = (16 ** len(component)) - 1
    return round(value / max_value * 255)
