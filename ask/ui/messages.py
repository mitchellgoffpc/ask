from ask.ui.components import Component, Box, Text
from ask.ui.styles import Flex, Colors, Styles, Theme


def Prompt(text: str, errors: list[str] | None = None) -> Component:
    return Box(margin={'bottom': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("> ", Theme.GRAY)),
            Text(Colors.hex(text, Theme.GRAY))
        ],
        *[Box(flex=Flex.HORIZONTAL)[
            Text(Colors.hex("  ⎿  ", Theme.GRAY)),
            Text(Colors.ansi(error, Colors.RED))
        ] for error in (errors or [])]
    ]

def TextResponse(text: str) -> Component:
    return Box(flex=Flex.HORIZONTAL, margin={'bottom': 1})[
        Text("⏺ "),
        Text(text)
    ]

def ToolResponse(tool: str, args: list[str], result: list[str], finished: bool = True) -> Component:
    args_str = ', '.join(args)
    args_str = f"({args_str})" if args_str else ""
    bullet = Colors.ansi("⏺", Colors.GREEN) if finished else "⏺"
    tool_str = f"{bullet} {Styles.bold(tool)}{args_str}…"
    return Text('\n'.join([tool_str] + ['⎿  ' + line for line in result]))
