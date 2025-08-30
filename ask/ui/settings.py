from typing import Callable

from ask.models import MODELS, Model
from ask.ui.components import Box, Text
from ask.ui.styles import Borders, Colors, Theme

class ModelSelector(Box):
    initial_state = {'selected_idx': 0}

    def __init__(self, active_model: Model, handle_select: Callable[[Model], None], handle_exit: Callable[[], None]) -> None:
        super().__init__(active_model=active_model, handle_select=handle_select, handle_exit=handle_exit)

    def handle_mount(self) -> None:
        self.state['selected_idx'] = next((i for i, m in enumerate(MODELS) if m == self.props['active_model']), 0)

    def handle_raw_input(self, ch: str) -> None:
        if ch in ('\x1b[A', '\x10'):  # Up arrow or Ctrl+P
            self.state['selected_idx'] = (self.state['selected_idx'] - 1) % len(self.props['models'])
        elif ch in ('\x1b[B', '\x0e'):  # Down arrow or Ctrl+N
            self.state['selected_idx'] = (self.state['selected_idx'] + 1) % len(self.props['models'])
        elif ch == '\x1b':  # Escape key
            self.props['handle_exit']()
        elif ch == '\r':  # Enter key
            idx = self.state['selected_idx']
            model = self.props['models'][idx]
            self.props['handle_select'](model)

    def contents(self) -> list:
        rows = []
        for idx, model in enumerate(MODELS):
            selected = idx == self.state['selected_idx']
            indicator = '* ' if model == self.props.get('active_model') else '  '
            text = f"{'❯ ' if selected else '  '}{indicator}{model.name}"
            rows.append(Text(Colors.hex(text, Theme.BLUE) if selected else text))

        return [
            Box(width=1.0, border_color=Colors.HEX(Theme.BLUE), border_style=Borders.ROUND, padding={'left': 1, 'right': 1}, margin={'top': 1})[
                Text(Colors.hex('Select a model', Theme.BLUE), margin={'bottom': 1}),
                Box()[rows],
                Text(Colors.hex('↑/↓ to navigate · enter to select · esc to exit', Theme.GRAY), margin={'top': 1})
            ]
        ]
