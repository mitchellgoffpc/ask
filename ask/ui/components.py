import shutil
from typing import Self, Literal
from ask.ui.styles import Colors, Borders, BorderStyle, ansi_len

Side = Literal['top', 'bottom', 'left', 'right']
Spacing = int | dict[Side, int]
Size = int | float | None

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


class Component:
    def __init__(self) -> None:
        self.children: list['Component'] = []

    def __getitem__(self, args: tuple['Component', ...]) -> Self:
        self.children = list(args)
        return self

    def render(self) -> str:
        return ''.join(child.render() for child in self.children)

    def handle_input(self, ch: str) -> None:
        for child in self.children:
            child.handle_input(ch)


class Text(Component):
    def __init__(self, text: str, margin: Spacing = 0) -> None:
        super().__init__()
        self.text = text
        self.margin = margin

    def __getitem__(self, args: tuple['Component', ...]) -> Self:
        raise NotImplementedError("Text components cannot have children")

    def render(self) -> str:
        return add_margin(self.text, self.margin)


class Box(Component):
    def __init__(
        self,
        width: Size = None,
        height: Size = None,
        margin: Spacing = 0,
        padding: Spacing = 0,
        border_color: str | None = None,
        border_style: BorderStyle = Borders.ROUND
    ) -> None:
        super().__init__()
        self.width = width
        self.height = height
        self.margin = margin
        self.padding = padding
        self.border_style = border_style
        self.border_color = border_color

    @property
    def box_width(self) -> int:
        if isinstance(self.width, int):
            return self.width  # absolute width
        elif isinstance(self.width, float):
            return int(self.width * terminal_width)  # percentage width
        else:
            return 0  # needs to be resolved in render method

    @property
    def box_height(self) -> int:
        if isinstance(self.height, int):
            return self.height  # absolute height
        elif isinstance(self.height, float):
            return int(self.height * terminal_height)  # percentage
        else:
            return 0  # needs to be resolved in render method

    @property
    def content_width(self) -> int:
        return max(0, self.box_width - 2)

    @property
    def content_height(self) -> int:
        return max(0, self.box_height - 2)

    def render_contents(self) -> str:
        return '\n'.join(child.render() for child in self.children)

    def render(self) -> str:
        content = self.render_contents()
        content = add_margin(content, self.padding) if self.padding is not None else content
        lines = content.split('\n')
        content_width = max(ansi_len(line) for line in lines)
        width = self.content_width or content_width
        height = self.content_height or len(lines)
        color_code = self.border_color or ''

        top_border = Colors.ansi(self.border_style.top_left + self.border_style.top * width + self.border_style.top_right, color_code)
        bottom_border = Colors.ansi(self.border_style.bottom_left + self.border_style.bottom * width + self.border_style.bottom_right, color_code)

        rendered_lines = [top_border]
        for i in range(height):
            line = lines[i] if i < len(lines) else ''
            line_content = line + ' ' * (width - ansi_len(line))
            rendered_lines.append(Colors.ansi(self.border_style.left, color_code) + line_content + Colors.ansi(self.border_style.right, color_code))
        rendered_lines.append(bottom_border)
        rendered = '\n'.join(rendered_lines)
        return add_margin(rendered, self.margin) if self.margin is not None else rendered
