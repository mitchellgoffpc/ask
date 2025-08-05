from functools import wraps
from threading import Thread
from typing import Any, Callable, Literal, Iterable, Optional, Self, Union, get_args
from uuid import UUID, uuid4

from ask.ui.styles import Colors, BorderStyle, Flex, ansi_len, ansi_slice

Side = Literal['top', 'bottom', 'left', 'right']
Spacing = int | dict[Side, int]
Size = int | float | None
TextCallback = Callable[[str], None]
BoolCallback = Callable[[bool], None]

dirty: set[UUID] = set()
nodes: dict[UUID, 'Component'] = {}
parents: dict[UUID, 'Component'] = {}
children: dict[UUID, list[Optional['Component']]] = {}
threads: dict[UUID, Thread] = {}

def get_rendered_width(contents: str) -> int:
    return max(ansi_len(line) for line in contents.split('\n'))

def get_spacing_dict(spacing: Spacing) -> dict[Side, int]:
    assert isinstance(spacing, (int, dict)), "Spacing must be an int or a dict with side keys"
    return {side: spacing if isinstance(spacing, int) else spacing.get(side, 0) for side in get_args(Side)}

def apply_sizing(content: str, width: int, height: int) -> str:
    lines = [ansi_slice(line, 0, width) + ' ' * max(0, width - ansi_len(line)) for line in content.split('\n')]
    lines = lines[:height] + [' ' * width] * max(0, height - len(lines))
    return '\n'.join(lines)

def apply_spacing(content: str, spacing: dict[Side, int]) -> str:
    lines = content.split('\n')
    width = (ansi_len(lines[0]) if lines else 0) + spacing['left'] + spacing['right']
    top_spacing = (' ' * width + '\n') * spacing.get('top', 0)
    bottom_spacing = ('\n' + ' ' * width) * spacing.get('bottom', 0)
    left_spacing = ' ' * spacing.get('left', 0)
    right_spacing = ' ' * spacing.get('right', 0)
    return top_spacing + '\n'.join(left_spacing + line + right_spacing for line in lines) + bottom_spacing

def apply_borders(content: str, width: int, border_style: BorderStyle | None, border_color: str | None) -> str:
    if border_style is not None:
        color_code = border_color or ''
        lines = content.split('\n') if content else []
        top_border = Colors.ansi(border_style.top_left + border_style.top * width + border_style.top_right, color_code)
        bottom_border = Colors.ansi(border_style.bottom_left + border_style.bottom * width + border_style.bottom_right, color_code)
        left_border = Colors.ansi(border_style.left, color_code)
        right_border = Colors.ansi(border_style.right, color_code)
        content = '\n'.join([top_border] + [left_border + line + right_border for line in lines] + [bottom_border])
    return content

def apply_boxing(content: str, max_width: int, component: 'Component') -> str:
    content_width = component.get_content_width(max_width) if component.props.get('width') is not None else get_rendered_width(content)
    content_height: int = component.props['height'] if component.props.get('height') is not None else content.count('\n') + 1 if content else 0
    padded_width = content_width + component.padding['left'] + component.padding['right']

    content = apply_sizing(content, content_width, content_height)
    content = apply_spacing(content, component.padding)
    content = apply_borders(content, padded_width, component.props.get('border_style'), component.props.get('border_color'))
    content = apply_spacing(content, component.margin)
    return content

def wrap_lines(content: str, max_width: int) -> str:
    lines = []
    paragraphs = content.split('\n')
    for paragraph in paragraphs:
        if paragraph == '':
            lines.append('')
        else:
            start = 0
            while start < ansi_len(paragraph):
                end = min(start + max_width, ansi_len(paragraph))
                lines.append(ansi_slice(paragraph, start, end))
                start = end
    return '\n'.join(lines)

def asyncronous(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        uuid = uuid4()
        threads[uuid] = Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        threads[uuid].start()
    return wrapper


class State:
    def __init__(self, uuid: UUID, state: dict[str, Any]) -> None:
        self.uuid = uuid
        self.state = state.copy()

    def __repr__(self) -> str:
        return f'State({self.state})'

    def __getitem__(self, key: str) -> Any:
        return self.state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if self.state.get(key) != value:
            dirty.add(self.uuid)
        self.state[key] = value

    def update(self, state: dict[str, Any]) -> None:
        for key, value in state.items():
            self[key] = value


class Component:
    leaf = False
    initial_state: dict[str, Any] = {}

    def __init__(self, **props: Any) -> None:
        self.children: list['Component'] = []
        self.uuid = uuid4()
        self.props = props
        self.state = State(self.uuid, self.initial_state)
        self.mounted = False
        self.rendered_width = 0

    def __getitem__(self, args: Union['Component', tuple['Component', ...], Iterable['Component']]) -> Self:
        if self.leaf:
            raise ValueError(f'{self.__class__.__name__} component is a leaf node and cannot have children')
        self.children = [args] if isinstance(args, Component) else list(args)
        return self

    @property
    def margin(self) -> dict[Side, int]:
        return get_spacing_dict(self.props.get('margin', 0))

    @property
    def padding(self) -> dict[Side, int]:
        return get_spacing_dict(self.props.get('padding', 0))

    @property
    def border_thickness(self) -> int:
        return 1 if self.props.get('border_style') is not None else 0

    def get_content_width(self, width: int) -> int:
        horizontal_padding = self.padding['left'] + self.padding['right']
        horizontal_margin = self.margin['left'] + self.margin['right']
        return max(0, width - horizontal_padding - horizontal_margin - self.border_thickness * 2)

    def contents(self) -> list['Component']:
        if self.leaf:
            return []
        raise NotImplementedError(f"{self.__class__.__name__} component must implement `contents` method")

    def render(self, contents: list[str], max_width: int) -> str:
        raise NotImplementedError(f"{self.__class__.__name__} component must implement `render` method")

    def handle_mount(self):
        self.mounted = True

    def handle_unmount(self):
        self.mounted = False

    def handle_update(self, new_props: dict[str, Any]) -> None:
        pass

    def handle_raw_input(self, ch: str) -> None:
        pass


class Text(Component):
    leaf = True

    def __init__(
        self,
        text: str,
        width: Size = None,
        height: Size = None,
        margin: Spacing = 0,
        padding: Spacing = 0,
        **props: Any
    ) -> None:
        super().__init__(text=text, width=width, height=height, margin=margin, padding=padding, **props)

    def render(self, _: list[str], max_width: int) -> str:
        wrapped = wrap_lines(self.props['text'], max_width)
        return apply_boxing(wrapped, max_width, self)


class Box(Component):
    def __init__(
        self,
        flex: Flex = Flex.VERTICAL,
        width: Size = None,
        height: Size = None,
        margin: Spacing = 0,
        padding: Spacing = 0,
        border_color: str | None = None,
        border_style: BorderStyle | None = None,
        **props: Any
    ) -> None:
        super().__init__(flex=flex, width=width, height=height, margin=margin, padding=padding, border_color=border_color, border_style=border_style, **props)

    def contents(self) -> list[Component]:
        return self.children

    def render(self, contents: list[str], max_width: int) -> str:
        if self.props['flex'] is Flex.VERTICAL:
            content = '\n'.join(contents)
        elif self.props['flex'] is Flex.HORIZONTAL:
            max_child_height = max((child.count('\n') + 1 for child in contents), default=0)
            contents = [apply_sizing(child, width=get_rendered_width(child), height=max_child_height) for child in contents]
            lines = [child.split('\n') for child in contents]
            content = '\n'.join(''.join(columns) for columns in zip(*lines, strict=True))

        return apply_boxing(content, max_width, self)
