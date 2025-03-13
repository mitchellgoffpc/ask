import uuid
import shutil
from typing import Any, Self, Literal
from ask.ui.styles import Colors, Borders, BorderStyle, ansi_len

Side = Literal['top', 'bottom', 'left', 'right']
Spacing = int | dict[Side, int]
Size = int | float | None

dirty = set()

terminal_width = shutil.get_terminal_size().columns
terminal_height = shutil.get_terminal_size().lines
def update_terminal_width() -> None:
    global terminal_width, terminal_height
    terminal_size = shutil.get_terminal_size()
    terminal_width = terminal_size.columns
    terminal_height = terminal_size.lines

def add_margin(text: str, margin: Spacing) -> str:
    if isinstance(margin, int):
        margin = {'top': margin, 'bottom': margin, 'left': margin, 'right': margin}
    lines = text.split('\n')
    top_margin = '\n' * margin.get('top', 0)
    bottom_margin = '\n' * margin.get('bottom', 0)
    left_margin = ' ' * margin.get('left', 0)
    right_margin = ' ' * margin.get('right', 0)
    return top_margin + '\n'.join(left_margin + line + right_margin for line in lines) + bottom_margin


class State:
    def __init__(self, uuid: uuid.UUID, state: dict[str, Any] = {}) -> None:
        self.uuid = uuid
        self.state = state

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

    def handle_input(self, ch: str) -> None:
        pass


class Text(Component):
    leaf = True

    def __init__(self, text: str, margin: Spacing = 0) -> None:
        super().__init__(text=text, margin=margin)

    def render(self, _: list[str]) -> str:
        return add_margin(self.props['text'], self.props['margin'])


class Box(Component):
    def __init__(
        self,
        width: Size = None,
        height: Size = None,
        margin: Spacing = 0,
        padding: Spacing = 0,
        border_color: str | None = None,
        border_style: BorderStyle = Borders.ROUND,
        **props: Any
    ) -> None:
        super().__init__(width=width, height=height, margin=margin, padding=padding, border_color=border_color, border_style=border_style, **props)

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
    def content_width(self) -> int:
        return max(0, self.box_width - 2)

    @property
    def content_height(self) -> int:
        return max(0, self.box_height - 2)

    def contents(self) -> list[Component]:
        return self.children

    def render(self, contents: list[str]) -> str:
        content = '\n'.join(contents)
        content = add_margin(content, self.props['padding']) if self.props.get('padding') else content
        lines = content.split('\n')
        content_width = max(ansi_len(line) for line in lines)
        width = self.content_width or content_width
        height = self.content_height or len(lines)
        color_code = self.props.get('border_color', '')
        border_style = self.props.get('border_style', Borders.ROUND)

        top_border = Colors.ansi(border_style.top_left + border_style.top * width + border_style.top_right, color_code)
        bottom_border = Colors.ansi(border_style.bottom_left + border_style.bottom * width + border_style.bottom_right, color_code)

        rendered_lines = [top_border]
        for i in range(height):
            line = lines[i] if i < len(lines) else ''
            line_content = line + ' ' * (width - ansi_len(line))
            rendered_lines.append(Colors.ansi(border_style.left, color_code) + line_content + Colors.ansi(border_style.right, color_code))
        rendered_lines.append(bottom_border)
        rendered = '\n'.join(rendered_lines)
        return add_margin(rendered, self.props['margin']) if self.props.get('margin') else rendered
