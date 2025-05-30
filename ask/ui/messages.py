from ask.ui.components import Text, get_terminal_size, wrap_lines, apply_spacing
from ask.ui.styles import Colors, Styles


class Prompt(Text):
    def __init__(self, text: str) -> None:
        super().__init__(text=text, margin={'bottom': 1})

    @property
    def text(self) -> str:
        return Colors.ansi(f"> {self.props['text']}", Colors.BLACK_BRIGHT)


class TextResponse(Text):
    def __init__(self, text: str) -> None:
        super().__init__(text=text, margin={'bottom': 1})

    @property
    def text(self) -> str:
        terminal_width, _ = get_terminal_size()
        text = '\n'.join(wrap_lines(self.props['text'], terminal_width - 2))
        text = apply_spacing(text, {'left': 2})
        return f"⏺ {text[2:]}"


class ToolResponse(Text):
    def __init__(self, tool: str, args: list[str], result: list[str], finished: bool = True) -> None:
        super().__init__(text="", margin={'bottom': 1})
        self.props.update(tool=tool, args=args, result=result, finished=finished)

    @property
    def text(self) -> str:
        args_str = ', '.join(self.props['args'])
        args_str = f"({args_str})" if args_str else ""
        bullet = Colors.ansi("⏺", Colors.GREEN) if self.props['finished'] else "⏺"
        tool_str = f"{bullet} {Styles.bold(self.props['tool'])}{args_str}…"
        return '\n'.join([tool_str] + ['⎿  ' + line for line in self.props['result']])
