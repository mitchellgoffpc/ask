from __future__ import annotations
from typing import Callable, ClassVar, Generic, Literal, Iterable, Self, Sequence, TypeVar, get_args
from uuid import UUID, uuid4

from ask.ui.core.styles import Borders, Colors, BorderStyle, Flex, ansi_len, ansi_slice, wrap_lines

Side = Literal['top', 'bottom', 'left', 'right']
Spacing = int | dict[Side, int]
Size = int | float | None

dirty: set[UUID] = set()
nodes: dict[UUID, Component] = {}
parents: dict[UUID, UUID] = {}
children: dict[UUID, list[Component | None]] = {}

def get_rendered_width(contents: str) -> int:
    return max(ansi_len(line) for line in contents.split('\n'))

def get_spacing_dict(spacing: Spacing) -> dict[Side, int]:
    assert isinstance(spacing, (int, dict)), "Spacing must be an int or a dict with side keys"
    return {side: spacing if isinstance(spacing, int) else spacing.get(side, 0) for side in get_args(Side)}

def apply_background(content: str, width: int, background_color: str | None) -> str:
    if not background_color:
        return content
    lines = content.split('\n')
    assert all(ansi_len(line) == width for line in lines), "All lines must have the same width for background to be applied"
    return '\n'.join(Colors.bg_ansi(line, background_color) for line in lines)

def apply_sizing(content: str, width: int, height: int) -> str:
    lines = [ansi_slice(line, 0, width) + ' ' * max(0, width - ansi_len(line)) for line in content.split('\n')]
    lines = lines[:height] + [' ' * width] * max(0, height - len(lines))
    return '\n'.join(lines)

def apply_spacing(content: str, spacing: dict[Side, int]) -> str:
    lines = content.split('\n')
    line_width = ansi_len(lines[0]) if lines else 0
    assert all(ansi_len(line) == line_width for line in lines), "All lines must have the same width for spacing to be applied"
    width = line_width + spacing['left'] + spacing['right']
    top_spacing = (' ' * width + '\n') * spacing['top']
    bottom_spacing = ('\n' + ' ' * width) * spacing['bottom']
    left_spacing = ' ' * spacing['left']
    right_spacing = ' ' * spacing['right']
    return top_spacing + '\n'.join(left_spacing + line + right_spacing for line in lines) + bottom_spacing

def apply_borders(content: str, width: int, borders: set[Side], border_style: BorderStyle, border_color: str | None) -> str:
    if not borders:
        return content
    color_code = border_color or ''
    lines = content.split('\n') if content else []
    assert all(ansi_len(line) == width for line in lines), "All lines must have the same width for borders to be applied"

    top_left = border_style.top_left if borders >= {'top', 'left'} else ''
    top_right = border_style.top_right if borders >= {'top', 'right'} else ''
    bottom_left = border_style.bottom_left if borders >= {'bottom', 'left'} else ''
    bottom_right = border_style.bottom_right if borders >= {'bottom', 'right'} else ''

    top_border = [Colors.ansi(top_left + border_style.top * width + top_right, color_code)] if 'top' in borders else []
    bottom_border = [Colors.ansi(bottom_left + border_style.bottom * width + bottom_right, color_code)] if 'bottom' in borders else []
    left_border = Colors.ansi(border_style.left, color_code) if 'left' in borders else ''
    right_border = Colors.ansi(border_style.right, color_code) if 'right' in borders else ''
    return '\n'.join(top_border + [left_border + line + right_border for line in lines] + bottom_border)

def apply_boxing(content: str, max_width: int, element: Element) -> str:
    max_content_width = element.get_content_width(max_width)
    if isinstance(element.width, int):
        content_width = min(max_content_width, element.get_content_width(element.width + element.margin['left'] + element.margin['right']))
    elif isinstance(element.width, float):
        content_width = max_content_width
    else:
        content_width = min(max_content_width, get_rendered_width(content))
    content_height: int = element.height if element.height is not None else content.count('\n') + 1 if content else 0
    padded_width = content_width + element.padding['left'] + element.padding['right']

    content = apply_sizing(content, content_width, content_height)
    content = apply_spacing(content, element.padding)
    content = apply_background(content, padded_width, element.background_color)
    content = apply_borders(content, padded_width, {k for k, v in element.border.items() if v}, element.border_style, element.border_color)
    content = apply_spacing(content, element.margin)
    return content


class Component:
    uuid: UUID
    def contents(self) -> list[Component | None]:
        raise NotImplementedError()

class Element(Component):
    def __init__(
        self,
        width: Size,
        height: int | None,
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
        self.rendered_width = 0

    def __getitem__(self, args: Component | Iterable[Component | None] | None) -> Self:
        self.children = [args] if isinstance(args, Component) else list(args) if args else []
        return self

    def get_content_width(self, width: int) -> int:
        horizontal_padding = self.padding['left'] + self.padding['right']
        horizontal_margin = self.margin['left'] + self.margin['right']
        horizontal_border = self.border['left'] + self.border['right']
        return max(0, width - horizontal_padding - horizontal_margin - horizontal_border)

    def contents(self) -> list[Component | None]:
        return self.children

    def render(self, contents: list[str], max_width: int) -> str:
        raise NotImplementedError()


class Text(Element):
    def __init__(
        self,
        text: str,
        width: Size = None,
        height: int | None = None,
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

    def __getitem__(self, args: Component | Iterable[Component | None] | None) -> Self:
        raise ValueError(f'{self.__class__.__name__} component is a leaf node and cannot have children')

    def render(self, _: list[str], max_width: int) -> str:
        wrapped = wrap_lines(self.text.replace('\t', ' ' * 8), max_width)
        return apply_boxing(wrapped, max_width, self)


class Box(Element):
    def __init__(
        self,
        flex: Flex = Flex.VERTICAL,
        width: Size = None,
        height: int | None = None,
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

    def render(self, contents: list[str], max_width: int) -> str:
        if self.flex is Flex.VERTICAL:
            content = '\n'.join(x for x in contents if x)
        elif self.flex is Flex.HORIZONTAL:
            max_child_height = max((child.count('\n') + 1 for child in contents), default=0)
            contents = [apply_sizing(child, width=get_rendered_width(child), height=max_child_height) for child in contents]
            lines = [child.split('\n') for child in contents]
            content = '\n'.join(''.join(columns) for columns in zip(*lines, strict=True))

        return apply_boxing(content, max_width, self)


ComponentType = TypeVar('ComponentType')

class Controller(Component, Generic[ComponentType]):
    state: list[str] = []

    def __init__(self, props: ComponentType) -> None:
        self.props = props
        self.uuid = uuid4()
        self.mounted = False

    def __call__(self, props: ComponentType) -> None:
        self.props = props

    def __setattr__(self, key, value):
        if key in self.state:
            dirty.add(self.uuid)
        super().__setattr__(key, value)

    def handle_mount(self):
        self.mounted = True

    def handle_unmount(self):
        self.mounted = False

    def handle_input(self, ch: str) -> None:
        pass

    def contents(self) -> list[Component | None]:
        raise NotImplementedError()

class Widget(Component):
    __controller__: ClassVar[Callable[[Self], type[Controller]]]
    __controller_instance__: Controller | None = None

    @property
    def controller(self) -> Controller:
        assert self.__controller_instance__ is not None, "Widget's controller instance is not initialized"
        return self.__controller_instance__

    @controller.setter
    def controller(self, value: Controller | None) -> None:
        self.__controller_instance__ = value

    def contents(self) -> list[Component | None]:
        return self.controller.contents()

    @property
    def uuid(self) -> UUID:
        return self.controller.uuid

    @uuid.setter
    def uuid(self, value: UUID) -> None:
        self.controller.uuid = value
