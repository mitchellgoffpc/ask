import re

from ask.tools import TOOLS, Tool
from ask.ui.components import Component, Box, Text
from ask.ui.styles import Flex, Colors, Styles, Theme

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

def render_markdown(text: str) -> str:
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

def ShellCall(command: str, output: str, error: str, expanded: bool = True) -> Component:
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("! ", Theme.PINK)),
            Text(Colors.hex(command, Theme.GRAY))
        ],
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(get_shell_output(output, expanded))
        ] if output else None,
        Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(Colors.ansi(error, Colors.RED))
        ] if error else None
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
