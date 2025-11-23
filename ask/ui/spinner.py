import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar

from ask.tools import TOOLS, ToDoTool
from ask.ui.core.components import Component, Controller, Box, Text, Widget
from ask.ui.core.styles import Colors, Flex, Theme

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

    def handle_mount(self) -> None:
        super().handle_mount()
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
        todos, todo_tool = self.props.todos, TOOLS[ToDoTool.name]
        return [
            Text(spinner_text, margin={'top': 1}),
            Box(flex=Flex.HORIZONTAL)[
                Text("  ⎿  "),
                Text(todo_tool.render_response(todos, '') if self.props.expanded else todo_tool.render_short_response(todos, ''))
            ] if todos else None,
        ]
