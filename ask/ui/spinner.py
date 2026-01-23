import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar

from ask.ui.core.components import ElementTree, Component, Controller, Box, Text, Widget
from ask.ui.core.styles import Colors, Flex, Theme
from ask.ui.tools.todo import ToDos

@dataclass
class Spinner(Widget):
    __controller__: ClassVar = lambda _: SpinnerController
    todos: dict[str, Any] | None
    expanded: bool

class SpinnerController(Controller[Spinner]):
    state = ['spinner_state']
    frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    text = "Loading…"
    spinner_state = 0

    def handle_mount(self, tree: ElementTree) -> None:
        super().handle_mount(tree)
        asyncio.create_task(self.spin())

    async def spin(self) -> None:
        while self.mounted:
            self.spinner_state += 1
            await asyncio.sleep(0.05)

    def contents(self) -> list[Component | None]:
        spinner_char = self.frames[(self.spinner_state // 2) % len(self.frames)]

        # Calculate highlight position
        cycle_length = len(self.text) + 17
        highlight_pos = (self.spinner_state % cycle_length) - 2
        before = self.text[:max(0, highlight_pos)]
        window = self.text[max(0, highlight_pos):min(len(self.text), highlight_pos + 3)]
        after = self.text[min(len(self.text), highlight_pos + 3):]

        highlighted_text = Colors.hex(before, Theme.ORANGE) + Colors.hex(window, Theme.LIGHT_ORANGE) + Colors.hex(after, Theme.ORANGE)
        spinner_text = f"{Colors.hex(spinner_char, Theme.ORANGE)} {highlighted_text} {Colors.hex('(esc to interrupt)', Theme.GRAY)}"
        return [
            Text(spinner_text, margin={'top': 1}),
            Box(flex=Flex.HORIZONTAL)[
                Text("  ⎿  "),
                ToDos(self.props.todos, expanded=self.props.expanded)
            ] if self.props.todos else None,
        ]
