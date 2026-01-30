import asyncio
import fcntl
import os
import select
import shutil
import sys
import termios
import tty
from contextlib import contextmanager
from itertools import zip_longest
from typing import Iterator

from ask.ui.core.components import Side, Component, Element, Box, Text
from ask.ui.core.cursor import hide_cursor, show_cursor, erase_line, cursor_up
from ask.ui.core.layout import layout
from ask.ui.core.styles import Axis, Colors, BorderStyle, ansi_len, ansi_slice
from ask.ui.core.tree import ElementTree, depth, propogate, mount, update

# Context manager to set O_NONBLOCK on a file descriptor
@contextmanager
def nonblocking(fd: int) -> Iterator[None]:
    original_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    try:
        fcntl.fcntl(fd, fcntl.F_SETFL, original_fl | os.O_NONBLOCK)
        yield
    finally:
        fcntl.fcntl(fd, fcntl.F_SETFL, original_fl)


# Rendering

def apply_background(content: str, width: int, background_color: str | None) -> str:
    if not background_color:
        return content
    lines = content.split('\n')
    assert all(ansi_len(line) == width for line in lines), "All lines must have the same width for background to be applied"
    return '\n'.join(Colors.bg_ansi(line, background_color) for line in lines)

def apply_sizing(content: str, width: int, height: int) -> str:
    lines = [ansi_slice(line, 0, width) + ' ' * max(0, width - ansi_len(line)) for line in content.split('\n')]
    lines = lines[:height] + [' ' * width] * max(0, height - len(lines))
    return '\n'.join(lines)

def apply_spacing(content: str, spacing: dict[Side, int]) -> str:
    lines = content.split('\n')
    line_width = ansi_len(lines[0]) if lines else 0
    assert all(ansi_len(line) == line_width for line in lines), "All lines must have the same width for spacing to be applied"
    width = line_width + spacing['left'] + spacing['right']
    top_spacing = (' ' * width + '\n') * spacing['top']
    bottom_spacing = ('\n' + ' ' * width) * spacing['bottom']
    left_spacing = ' ' * spacing['left']
    right_spacing = ' ' * spacing['right']
    return top_spacing + '\n'.join(left_spacing + line + right_spacing for line in lines) + bottom_spacing

def apply_borders(content: str, width: int, borders: set[Side], border_style: BorderStyle, border_color: str | None) -> str:
    if not borders:
        return content
    color_code = border_color or ''
    lines = content.split('\n') if content else []
    assert all(ansi_len(line) == width for line in lines), "All lines must have the same width for borders to be applied"

    top_left = border_style.top_left if borders >= {'top', 'left'} else ''
    top_right = border_style.top_right if borders >= {'top', 'right'} else ''
    bottom_left = border_style.bottom_left if borders >= {'bottom', 'left'} else ''
    bottom_right = border_style.bottom_right if borders >= {'bottom', 'right'} else ''

    top_border = [Colors.ansi(top_left + border_style.top * width + top_right, color_code)] if 'top' in borders else []
    bottom_border = [Colors.ansi(bottom_left + border_style.bottom * width + bottom_right, color_code)] if 'bottom' in borders else []
    left_border = Colors.ansi(border_style.left, color_code) if 'left' in borders else ''
    right_border = Colors.ansi(border_style.right, color_code) if 'right' in borders else ''
    return '\n'.join(top_border + [left_border + line + right_border for line in lines] + bottom_border)

def apply_boxing(content: str, content_width: int, content_height: int, element: Element) -> str:
    padded_width = content_width + element.padding['left'] + element.padding['right']
    content = apply_sizing(content, content_width, content_height)
    content = apply_spacing(content, element.padding)
    content = apply_background(content, padded_width, element.background_color)
    content = apply_borders(content, padded_width, {k for k, v in element.border.items() if v}, element.border_style, element.border_color)
    content = apply_spacing(content, element.margin)
    return content

def render(tree: ElementTree, element: Element) -> str:
    content_width = max(0, tree.widths[element.uuid] - element.chrome(Axis.HORIZONTAL))
    content_height = max(0, tree.heights[element.uuid] - element.chrome(Axis.VERTICAL))

    match element:
        case Text():
            content = element.wrap(content_width)
        case Box():
            collapsed = tree.collapsed_children[element.uuid]
            contents = [render(tree, child) for child in collapsed]
            if element.flex is Axis.VERTICAL:
                content = '\n'.join(x for x in contents if x)
            else:
                max_child_height = max((tree.heights[child.uuid] for child in collapsed), default=0)
                contents = [apply_sizing(child_content, tree.widths[child.uuid], max_child_height)
                            for child_content, child in zip(contents, collapsed, strict=True)]
                lines = [child.split('\n') for child in contents]
                content = '\n'.join(''.join(columns) for columns in zip(*lines, strict=True))
        case _:
            raise ValueError(f"Unknown element type: {type(element)}")

    return apply_boxing(content, content_width, content_height, element)


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
                propogate(tree, root, sequence, 'input')

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
