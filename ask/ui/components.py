import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from queue import PriorityQueue, Queue
from typing import Any, Callable, Iterator, Literal, Self, get_args

from ask.ui.styles import Colors, Borders, BorderStyle, ansi_len, ansi_slice

Side = Literal['top', 'bottom', 'left', 'right']
Spacing = int | dict[Side, int]
Size = int | float | None

dirty: set[uuid.UUID] = set()
events: PriorityQueue['AsyncEvent'] = PriorityQueue()
generators: dict[uuid.UUID, 'AsyncGenerator'] = {}

terminal_width = shutil.get_terminal_size().columns
terminal_height = shutil.get_terminal_size().lines

def get_terminal_size() -> tuple[int, int]:
    return terminal_width, terminal_height

def update_terminal_width() -> None:
    global terminal_width, terminal_height
    terminal_size = shutil.get_terminal_size()
    terminal_width = terminal_size.columns
    terminal_height = terminal_size.lines

def get_spacing_dict(spacing: Spacing) -> dict[Side, int]:
    assert isinstance(spacing, (int, dict)), "Spacing must be an int or a dict with side keys"
    return {side: spacing if isinstance(spacing, int) else spacing.get(side, 0) for side in get_args(Side)}

def apply_spacing(text: str, spacing: dict[Side, int]) -> str:
    lines = text.split('\n')
    top_spacing = '\n' * spacing.get('top', 0)
    bottom_spacing = '\n' * spacing.get('bottom', 0)
    left_spacing = ' ' * spacing.get('left', 0)
    right_spacing = ' ' * spacing.get('right', 0)
    return top_spacing + '\n'.join(left_spacing + line + right_spacing for line in lines) + bottom_spacing

def wrap_lines(content: str, max_width: int) -> list[str]:
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
    return lines

def generator_thread(it: Iterator[Any], result_queue: Queue, cancel_event: threading.Event) -> None:
    try:
        for item in it:
            if cancel_event.is_set():
                break
            result_queue.put(item)
    except Exception as e:
        result_queue.put(e)


@dataclass(order=True)
class AsyncEvent:
    time: float
    callback: Callable = field(compare=False)

@dataclass
class AsyncGenerator:
    thread: threading.Thread
    result_queue: Queue
    cancel_event: threading.Event
    callback: Callable


class State:
    def __init__(self, uuid: uuid.UUID, state: dict[str, Any]) -> None:
        self.uuid = uuid
        self.state = state.copy()

    def __repr__(self) -> str:
        return f'State({self.state})'

    def __getitem__(self, key: str) -> Any:
        return self.state.get(key)

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
        self.uuid = uuid.uuid4()
        self.props = props
        self.state = State(self.uuid, self.initial_state)

    def __getitem__(self, args: tuple['Component', ...]) -> Self:
        if self.leaf:
            raise ValueError(f'{self.__class__.__name__} component is a leaf node and cannot have children')
        self.children = list(args)
        return self

    def contents(self) -> list['Component']:
        if self.leaf:
            return []
        raise NotImplementedError(f"{self.__class__.__name__} component must implement `contents` method")

    def render(self, contents: list[str]) -> str:
        return '\n'.join(contents)

    def handle_update(self, new_props: dict[str, Any]) -> None:
        pass

    def handle_input(self, ch: str) -> None:
        pass

    def async_call(self, callback: Callable, delay_seconds: float = 0) -> None:
        events.put(AsyncEvent(time.monotonic() + delay_seconds, callback))

    def async_map(self, callback: Callable, it: Iterator[Any]) -> uuid.UUID:
        generator_id = uuid.uuid4()
        result_queue: Queue = Queue()
        cancel_event = threading.Event()
        thread = threading.Thread(target=generator_thread, args=(it, result_queue, cancel_event))
        generators[generator_id] = AsyncGenerator(thread, result_queue, cancel_event, callback)
        thread.start()
        return generator_id


class Text(Component):
    leaf = True

    def __init__(self, text: str, margin: Spacing = 0) -> None:
        super().__init__(text=text, margin=margin)

    @property
    def text(self) -> str:
        text: str = self.props['text']
        return text

    def render(self, _: list[str]) -> str:
        return apply_spacing(self.text, get_spacing_dict(self.props['margin']))


class Box(Component):
    def __init__(
        self,
        width: Size = None,
        height: Size = None,
        margin: Spacing = 0,
        padding: Spacing = 0,
        border_color: str | None = None,
        border_style: BorderStyle | None = Borders.ROUND,
        **props: Any
    ) -> None:
        super().__init__(
            width=width,
            height=height,
            margin=margin,
            padding=padding,
            border_color=border_color,
            border_style=border_style,
            **props
        )

    @property
    def border_thickness(self) -> int:
        return 1 if self.props.get('border_style') is not None else 0

    @property
    def box_width(self) -> int:
        width = self.props.get('width')
        if isinstance(width, int):
            return width  # absolute width
        elif isinstance(width, float):
            return int(width * terminal_width)  # percentage width
        else:
            return 0  # needs to be resolved in render method

    @property
    def box_height(self) -> int:
        height = self.props.get('height')
        if isinstance(height, int):
            return height  # absolute height
        elif isinstance(height, float):
            return int(height * terminal_height)  # percentage
        else:
            return 0  # needs to be resolved in render method

    @property
    def padded_width(self) -> int:
        return max(0, self.box_width - self.border_thickness * 2)

    @property
    def padded_height(self) -> int:
        return max(0, self.box_height - self.border_thickness * 2)

    @property
    def content_width(self) -> int:
        horizontal_padding = self.padding['left'] + self.padding['right']
        return max(0, self.padded_width - horizontal_padding)

    @property
    def content_height(self) -> int:
        vertical_padding = self.padding['top'] + self.padding['bottom']
        return max(0, self.padded_height - vertical_padding)

    @property
    def margin(self) -> dict[Side, int]:
        return get_spacing_dict(self.props['margin'])

    @property
    def padding(self) -> dict[Side, int]:
        return get_spacing_dict(self.props['padding'])

    def contents(self) -> list[Component]:
        return self.children

    def render(self, contents: list[str]) -> str:
        if self.content_width:
            contents = wrap_lines('\n'.join(contents), self.content_width)
        content = apply_spacing('\n'.join(contents), self.padding)
        lines = content.split('\n') if content else []
        width = self.padded_width or max((ansi_len(line) for line in lines), default=0)
        height = self.padded_height or len(lines)
        border_style = self.props.get('border_style', Borders.ROUND)

        # Render the content lines without borders
        rendered_lines = []
        for i in range(height):
            line = lines[i] if i < len(lines) else ''
            line_content = line + ' ' * (width - ansi_len(line))
            rendered_lines.append(line_content)

        # Add borders if specified
        if border_style is not None:
            color_code = self.props.get('border_color') or ''
            top_border = Colors.ansi(border_style.top_left + border_style.top * width + border_style.top_right, color_code)
            bottom_border = Colors.ansi(border_style.bottom_left + border_style.bottom * width + border_style.bottom_right, color_code)
            left_border = Colors.ansi(border_style.left, color_code)
            right_border = Colors.ansi(border_style.right, color_code)
            rendered_lines = [top_border] + [left_border + line + right_border for line in rendered_lines] + [bottom_border]

        return apply_spacing('\n'.join(rendered_lines), self.margin)
