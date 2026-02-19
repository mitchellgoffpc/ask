from dataclasses import dataclass

from ask.ui.core.components import BaseController, Box, Component, Text, Widget


@dataclass
class WideTree(Widget):
    class Controller(BaseController):
        def contents(self) -> list[Component | None]:
            return [Box()[(Text(text=str(i), margin={'top': 1, 'left': 1}, border=['bottom', 'right']) for i in range(100))]]

@dataclass
class DeepTree(Widget):
    class Controller(BaseController):
        def contents(self) -> list[Component | None]:
            node: Component = Text(text='leaf', width=1.0)
            for _ in range(100):
                node = Box(margin={'top': 1, 'left': 1}, border=['bottom', 'right'])[node]
            return [node]
