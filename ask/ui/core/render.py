import asyncio
import fcntl
import os
import re
import select
import shutil
import sys
import termios
import tty
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import zip_longest

from ask.ui.core.components import Side, Component, Element, Box, Text
from ask.ui.core.cursor import hide_cursor, show_cursor, erase_line, cursor_up
from ask.ui.core.layout import layout
from ask.ui.core.styles import Axis, Colors, BorderStyle, ansi_len
from ask.ui.core.tree import ElementTree, depth, propogate, mount, update

CONTROL_SEQ_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z~]?|\x1b.|[\x00-\x1f\x7f]')

# Input parsing
def split_input_sequence(sequence: str) -> list[str]:
    chunks: list[str] = []
    last = 0
    for match in CONTROL_SEQ_RE.finditer(sequence):
        if match.start() > last:
            chunks.append(sequence[last:match.start()])
        chunks.append(match.group(0))
        last = match.end()
    if last < len(sequence):
        chunks.append(sequence[last:])
    return chunks

# Context manager to set O_NONBLOCK on a file descriptor
@contextmanager
def nonblocking(fd: int) -> Iterator[None]:
    original_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    try:
        fcntl.fcntl(fd, fcntl.F_SETFL, original_fl | os.O_NONBLOCK)
        yield
    finally:
        fcntl.fcntl(fd, fcntl.F_SETFL, original_fl)


# Rendering logic

def apply_spacing(rows: list[str], width: int, spacing: dict[Side, int]) -> list[str]:
    left = ' ' * spacing['left']
    right = ' ' * spacing['right']
    vertical = ' ' * (width + spacing['left'] + spacing['right'])
    return [vertical] * spacing['top'] + [left + row + right for row in rows] + [vertical] * spacing['bottom']

def apply_borders(rows: list[str], width: int, borders: set[Side], border_style: BorderStyle, border_color: str | None) -> list[str]:
    if not borders:
        return rows
    color_code = border_color or ''
    top_left = border_style.top_left if borders >= {'top', 'left'} else ''
    top_right = border_style.top_right if borders >= {'top', 'right'} else ''
    bottom_left = border_style.bottom_left if borders >= {'bottom', 'left'} else ''
    bottom_right = border_style.bottom_right if borders >= {'bottom', 'right'} else ''
    left_border = Colors.ansi(border_style.left, color_code) if 'left' in borders else ''
    right_border = Colors.ansi(border_style.right, color_code) if 'right' in borders else ''

    result = []
    if 'top' in borders:
        result.append(Colors.ansi(top_left + border_style.top * width + top_right, color_code))
    for row in rows:
        result.append(left_border + row + right_border)
    if 'bottom' in borders:
        result.append(Colors.ansi(bottom_left + border_style.bottom * width + bottom_right, color_code))
    return result

def apply_chrome(rows: list[str], content_width: int, element: Element) -> list[str]:
    padded_width = content_width + element.paddings['left'] + element.paddings['right']
    bordered_width = padded_width + element.borders['left'] + element.borders['right']
    rows = apply_spacing(rows, content_width, element.paddings)
    if element.background_color:
        rows = [element.background_color + row + Colors.BG_END for row in rows]
    rows = apply_borders(rows, padded_width, {k for k, v in element.borders.items() if v}, element.border_style, element.border_color)
    rows = apply_spacing(rows, bordered_width, element.margins)
    return rows

def _render(tree: ElementTree, element: Element) -> list[str]:
    content_width = tree.widths[element.uuid] - element.chrome(Axis.HORIZONTAL)
    content_height = tree.heights[element.uuid] - element.chrome(Axis.VERTICAL)

    match element:
        case Text():
            wrapped = element.wrapped(content_width)
            rows = [line + ' ' * (content_width - ansi_len(line)) for line in wrapped.split('\n')]
            rows = rows + [' ' * content_width for _ in range(content_height - len(rows))]
        case Box():
            children = tree.collapsed_children[element.uuid]
            child_rows = [_render(tree, child) for child in children]
            child_widths = [tree.widths[child.uuid] for child in children]

            if element.flex is Axis.VERTICAL:
                rows = []
                for crows, cwidth in zip(child_rows, child_widths, strict=True):
                    rows.extend([row + ' ' * (content_width - cwidth) for row in crows])
                rows = rows + [' ' * content_width for _ in range(content_height - len(rows))]
            else:
                for crows, cwidth in zip(child_rows, child_widths, strict=True):
                    crows.extend([' ' * cwidth for _ in range(content_height - len(crows))])
                remaining_width = content_width - sum(child_widths)
                child_rows.append([' ' * remaining_width for _ in range(content_height)])
                rows = [''.join(row_parts) for row_parts in zip(*child_rows, strict=True)]
        case _:
            raise ValueError(f"Unknown element type: {type(element)}")

    return apply_chrome(rows, content_width, element)

def render(tree: ElementTree, element: Element) -> str:
    return '\n'.join(_render(tree, element))


# Main render loop

async def render_root(_root: Component) -> None:
    hide_cursor()

    root = _root if isinstance(_root, Element) else Box()[_root]  # Root component needs to be an element
    tree = ElementTree(root)
    mount(tree, root)
    terminal_width = shutil.get_terminal_size().columns
    layout(tree, root, terminal_width)
    initial_render = render(tree, root)
    previous_render_lines = initial_render.split('\n')
    print('\n\r'.join(previous_render_lines))

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ready, _, _ = select.select([sys.stdin], [], [], 0.05)
            if ready:
                with nonblocking(fd):
                    sequence = ''
                    while (ch := sys.stdin.read(1)):
                        sequence += ch
                for chunk in split_input_sequence(sequence):
                    propogate(tree, root, chunk, 'input')

            # Check for dirty components
            if not tree.dirty:
                await asyncio.sleep(0.01)
                continue
            for uuid in sorted(tree.dirty, key=lambda uuid: depth(tree, tree.nodes[uuid])):  # start at the top and work downwards
                if uuid in tree.nodes:
                    update(tree, tree.nodes[uuid])
            tree.dirty.clear()

            # Re-render the tree
            terminal_size = shutil.get_terminal_size()
            layout(tree, root, terminal_size.columns)
            new_render_lines = render(tree, root).split('\n')

            # Check if we need to clear screen due to large difference in output size
            if len(previous_render_lines) - len(new_render_lines) > min(terminal_size.lines / 2, terminal_size.lines - 20):
                sys.stdout.write('\033c')
                previous_render_lines = []

            # Pad new render to match the number of previous lines
            max_lines = max(len(previous_render_lines), len(new_render_lines))
            new_render_lines.extend([''] * (max_lines - len(new_render_lines)))

            # If there are unchanged leading lines, move cursor to the first changed line
            line_diffs = zip_longest(previous_render_lines, new_render_lines, fillvalue='')
            first_diff_idx = next((i for i, (prev, new) in enumerate(line_diffs) if prev != new), None)
            if first_diff_idx is None:
                await asyncio.sleep(0.01)
                continue

            output = cursor_up(len(previous_render_lines) - first_diff_idx)
            for prev_line, new_line in zip_longest(previous_render_lines[first_diff_idx:], new_render_lines[first_diff_idx:], fillvalue=''):
                sys.stdout.write('\r')
                if ansi_len(new_line) < ansi_len(prev_line):
                    output += erase_line
                output += new_line + '\n\r'

            sys.stdout.write(output)
            sys.stdout.flush()
            previous_render_lines = new_render_lines
            await asyncio.sleep(0.01)

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        show_cursor()
        sys.stdout.write('\n')
        sys.stdout.flush()
