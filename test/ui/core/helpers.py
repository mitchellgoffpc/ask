from dataclasses import dataclass
from typing import ClassVar

from ask.ui.core.components import Component, Box, Text, Controller, Widget

@dataclass
class WideTree(Widget):
    __controller__: ClassVar = lambda _: WideTreeController

class WideTreeController(Controller[WideTree]):
    def contents(self) -> list[Component | None]:
        return [Box()[(Text(text=str(i), margin={'top': 1, 'left': 1}, border=['bottom', 'right']) for i in range(100))]]

@dataclass
class DeepTree(Widget):
    __controller__: ClassVar = lambda _: DeepTreeController

class DeepTreeController(Controller[DeepTree]):
    def contents(self) -> list[Component | None]:
        node: Component = Text(text='leaf', width=1.0)
        for _ in range(100):
            node = Box(margin={'top': 1, 'left': 1}, border=['bottom', 'right'])[node]
        return [node]
