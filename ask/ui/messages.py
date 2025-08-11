import re
import time
from typing import Any
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import TerminalFormatter, Terminal256Formatter, TerminalTrueColorFormatter
from pygments.util import ClassNotFound

from ask.tools import TOOLS, Tool
from ask.ui.components import Component, Box, Text
from ask.ui.styles import Flex, Colors, Styles, Theme, ANSI_256_SUPPORT, ANSI_16M_SUPPORT

NUM_PREVIEW_LINES = 5

def get_shell_output(result: str, expanded: bool) -> str:
    if not result:
        return Colors.hex("(No content)", Theme.GRAY)
    elif expanded:
        return result
    else:
        lines = result.rstrip('\n').split('\n')
        expand_text = Colors.hex(f"… +{len(lines) - NUM_PREVIEW_LINES} lines (ctrl+r to expand)", Theme.GRAY)
        return '\n'.join(lines[:NUM_PREVIEW_LINES]) + (f'\n{expand_text}' if len(lines) > NUM_PREVIEW_LINES else '')

def get_tool_result(tool: Tool, result: str, expanded: bool) -> str:
    if expanded:
        return tool.render_response(result)
    else:
        return f"{tool.render_short_response(result)} {Colors.hex('(ctrl+r to expand)', Theme.GRAY)}"

def render_markdown_text(text: str) -> str:
    # Code spans
    text = re.sub(r'`([^`]+)`', lambda m: Colors.hex(m.group(1), Theme.BLUE), text)
    # Bold
    text = re.sub(r'\*\*([^*]+)\*\*', lambda m: Styles.bold(m.group(1)), text)
    text = re.sub(r'__([^_]+)__', lambda m: Styles.bold(m.group(1)), text)
    # Italic
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', lambda m: Styles.italic(m.group(1)), text)
    text = re.sub(r'(?<!_)_([^_]+)_(?!_)', lambda m: Styles.italic(m.group(1)), text)
    # Headers
    text = re.sub(r'[^\S\n]*#{1,6}[^\S\n]*(.+)', lambda m: Styles.bold(m.group(1)) + '\n', text, flags=re.MULTILINE)
    return text

def render_code_block(code_block: str) -> str:
    match = re.match(r'```(\w+)?\n?(.*?)```', code_block, re.DOTALL)
    if not match:
        return code_block

    language, code = match.groups()
    formatter: Any
    if ANSI_16M_SUPPORT:
        formatter = TerminalTrueColorFormatter()
    elif ANSI_256_SUPPORT:
        formatter = Terminal256Formatter()
    else:
        formatter = TerminalFormatter()

    try:
        lexer = get_lexer_by_name(language)
    except ClassNotFound:
        lexer = guess_lexer(code)
    highlighted: str = highlight(code, lexer, formatter).rstrip('\n')
    return highlighted + '\n\n'

def render_markdown(text: str) -> str:
    parts = re.split(r'(```[^`]*```)', text)  # Split on code blocks (```...```)
    return ''.join(render_markdown_text(part) if i % 2 == 0 else render_code_block(part) for i, part in enumerate(parts))


# Components

def Prompt(text: str, errors: list[str] | None = None) -> Component:
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("> ", Theme.GRAY)),
            Text(Colors.hex(text, Theme.GRAY))
        ],
        *[Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("  ⎿  ", Theme.GRAY)),
            Text(Colors.ansi(error, Colors.RED))
        ] for error in (errors or [])]
    ]

def ShellCall(command: str, output: str | None, error: str | None, start_time: float, expanded: bool = True) -> Component:
    elapsed = int(time.time() - start_time)
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("! ", Theme.PINK)),
            Text(Colors.hex(command, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(Colors.hex(f"({elapsed}s)", Theme.GRAY)),
        ] if output is None and elapsed >= 1 else None,
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(get_shell_output(output, expanded))
        ] if output is not None else None,
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(Colors.ansi(error, Colors.RED))
        ] if output is not None and error else None,
    ]

def TextResponse(text: str) -> Component:
    return Box(flex=Flex.HORIZONTAL, margin={'top': 1})[
        Text("● "),
        Text(render_markdown(text))
    ]

def ToolCall(tool: str, args: dict[str, str], result: str | None, expanded: bool = True) -> Component:
    args_str = TOOLS[tool].render_args(args)

    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.ansi("● ", Colors.GREEN) if result is not None else "● "),
            Text(Styles.bold(tool) + (f"({args_str})" if args_str else ''))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(get_tool_result(TOOLS[tool], result, expanded))
        ] if result is not None else None,
    ]
