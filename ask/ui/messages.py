from ask.tools import TOOLS
from ask.ui.components import Component, Box, Text
from ask.ui.styles import Flex, Colors, Styles, Theme

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

def TextResponse(text: str) -> Component:
    return Box(flex=Flex.HORIZONTAL, margin={'top': 1})[
        Text("● "),
        Text(text)
    ]

def ToolCall(tool: str, args: dict[str, str], result: str | None) -> Component:
    args_str = TOOLS[tool].render_args(args)
    return Box(margin={'top': 1})[
        Box(flex=Flex.HORIZONTAL)[
            Text(Colors.ansi("● ", Colors.GREEN) if result is not None else "● "),
            Text(Styles.bold(tool) + (f"({args_str})" if args_str else ''))
        ],
        *([Box(flex=Flex.HORIZONTAL)[
            Text("  ⎿  "),
            Text(TOOLS[tool].render_response(result))
        ]] if result is not None else [])
    ]
