from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Literal, Self, TypeVar, get_args
from uuid import UUID, uuid4

from ask.ui.core.styles import Axis, Borders, BorderStyle, Wrap, wrap_lines

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
        raise NotImplementedError

@dataclass
class Element(Component):
    width: Length = field(default=None, kw_only=True)
    height: Length = field(default=None, kw_only=True)
    margin: Spacing = field(default=0, kw_only=True)
    padding: Spacing = field(default=0, kw_only=True)
    border: Sequence[Side] = field(default=(), kw_only=True)
    border_style: BorderStyle = field(default_factory=lambda: Borders.ROUND, kw_only=True)
    border_color: str | None = field(default=None, kw_only=True)
    background_color: str | None = field(default=None, kw_only=True)
    visible: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        self.margins = get_spacing_dict(self.margin)
        self.paddings = get_spacing_dict(self.padding)
        self.borders = {side: int(side in self.border) for side in get_args(Side)}
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
        return self.paddings[a] + self.paddings[b] + self.margins[a] + self.margins[b] + self.borders[a] + self.borders[b]

    def contents(self) -> list[Component | None]:
        return self.children

@dataclass
class Text(Element):
    text: str
    wrap: Wrap = field(default=Wrap.WORDS, kw_only=True)

    def __post_init__(self) -> None:
        super().__post_init__()
        self._wrap_cache: dict[int, str] = {}

    def __getitem__(self, args: Component | Iterable[Component | None] | None) -> Self:
        raise ValueError(f'{self.__class__.__name__} component is a leaf node and cannot have children')

    def wrapped(self, width: int) -> str:
        if width not in self._wrap_cache:
            self._wrap_cache[width] = wrap_lines(self.text.replace('\t', ' ' * 8), width, wrap=self.wrap)
        return self._wrap_cache[width]

@dataclass
class Box(Element):
    flex: Axis = Axis.VERTICAL


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

    def handle_update(self, new_props: ComponentType) -> None:
        self.props = new_props

    def handle_input(self, ch: str) -> None:
        pass

    @property
    def mounted(self) -> bool:
        return self.tree is not None

    def contents(self) -> list[Component | None]:
        raise NotImplementedError

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
