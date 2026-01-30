from __future__ import annotations
from typing import Any, ClassVar, Generic, Literal, Iterable, Self, Sequence, TypeVar, get_args, TYPE_CHECKING
from uuid import UUID, uuid4

from ask.ui.core.styles import Axis, Borders, BorderStyle, wrap_lines
if TYPE_CHECKING:
    from ask.ui.core.tree import ElementTree

Side = Literal['top', 'bottom', 'left', 'right']
Spacing = int | dict[Side, int]
Length = int | float | None

def get_spacing_dict(spacing: Spacing) -> dict[Side, int]:
    assert isinstance(spacing, (int, dict)), "Spacing must be an int or a dict with side keys"
    return {side: spacing if isinstance(spacing, int) else spacing.get(side, 0) for side in get_args(Side)}


class Component:
    uuid: UUID

    def contents(self) -> list[Component | None]:
        raise NotImplementedError()

class Element(Component):
    def __init__(
        self,
        width: Length,
        height: Length,
        margin: Spacing,
        padding: Spacing,
        border: Sequence[Side],
        border_color: str | None,
        border_style: BorderStyle,
        background_color: str | None,
    ) -> None:
        self.width, self.height = width, height
        self.margin = get_spacing_dict(margin)
        self.padding = get_spacing_dict(padding)
        self.border = {side: int(side in border) for side in get_args(Side)}
        self.border_color = border_color
        self.border_style = border_style
        self.background_color = background_color

        self.children: list[Component | None] = []
        self.uuid = uuid4()

    def __getitem__(self, args: Component | Iterable[Component | None] | None) -> Self:
        self.children = [args] if isinstance(args, Component) else list(args) if args else []
        return self

    def length(self, axis: Axis) -> Length:
        return self.width if axis is Axis.HORIZONTAL else self.height

    def chrome(self, axis: Axis) -> int:
        a: Side = 'left' if axis is Axis.HORIZONTAL else 'top'
        b: Side = 'right' if axis is Axis.HORIZONTAL else 'bottom'
        return self.padding[a] + self.padding[b] + self.margin[a] + self.margin[b] + self.border[a] + self.border[b]

    def contents(self) -> list[Component | None]:
        return self.children


class Text(Element):
    def __init__(
        self,
        text: str,
        width: Length = None,
        height: Length = None,
        margin: Spacing = 0,
        padding: Spacing = 0,
        border: Sequence[Side] = (),
        border_style: BorderStyle = Borders.ROUND,
        border_color: str | None = None,
        background_color: str | None = None,
    ) -> None:
        super().__init__(width=width, height=height, margin=margin, padding=padding,
                         border=border, border_color=border_color, border_style=border_style, background_color=background_color)
        self.text = text
        self._wrapped: dict[int, str] = {}

    def __getitem__(self, args: Component | Iterable[Component | None] | None) -> Self:
        raise ValueError(f'{self.__class__.__name__} component is a leaf node and cannot have children')

    def wrap(self, width: int) -> str:
        if width not in self._wrapped:
            self._wrapped[width] = wrap_lines(self.text.replace('\t', ' ' * 8), width)
        return self._wrapped[width]


class Box(Element):
    def __init__(
        self,
        flex: Axis = Axis.VERTICAL,
        width: Length = None,
        height: Length = None,
        margin: Spacing = 0,
        padding: Spacing = 0,
        border: Sequence[Side] = (),
        border_color: str | None = None,
        border_style: BorderStyle = Borders.ROUND,
        background_color: str | None = None,
    ) -> None:
        super().__init__(width=width, height=height, margin=margin, padding=padding,
                         border=border, border_color=border_color, border_style=border_style, background_color=background_color)
        self.flex = flex


ComponentType = TypeVar('ComponentType')

class BaseController(Component, Generic[ComponentType]):
    state: list[str] = []
    tree: ElementTree | None = None

    def __init_subclass__(cls: type[BaseController[ComponentType]], *args: Any, **kwargs: Any) -> None:
        super().__init_subclass__(*args, **kwargs)
        for base in getattr(cls, '__orig_bases__', []):
            for arg in get_args(base):
                if isinstance(arg, type) and issubclass(arg, Widget) and not hasattr(arg, 'Controller'):
                    arg.Controller = cls
                    return

    def __init__(self, props: ComponentType) -> None:
        self.props = props
        self.uuid = uuid4()

    def __call__(self, props: ComponentType) -> None:
        self.props = props

    def __setattr__(self, key: str, value: Any) -> None:
        if key in self.state:
            self.set_dirty()
        super().__setattr__(key, value)

    def set_dirty(self) -> None:
        if self.tree:
            self.tree.dirty.add(self.uuid)

    def handle_mount(self, tree: ElementTree) -> None:
        self.tree = tree

    def handle_unmount(self) -> None:
        self.tree = None

    def handle_input(self, ch: str) -> None:
        pass

    @property
    def mounted(self) -> bool:
        return self.tree is not None

    def contents(self) -> list[Component | None]:
        raise NotImplementedError()

class Widget(Component):
    Controller: ClassVar[type[BaseController]]
    _controller: BaseController | None = None

    @property
    def controller(self) -> BaseController:
        assert self._controller is not None, "Widget's controller instance is not initialized"
        return self._controller

    @controller.setter
    def controller(self, value: BaseController | None) -> None:
        self._controller = value

    @property
    def uuid(self) -> UUID:
        return self.controller.uuid

    @uuid.setter
    def uuid(self, value: UUID) -> None:
        self.controller.uuid = value

    def contents(self) -> list[Component | None]:
        return self.controller.contents()
