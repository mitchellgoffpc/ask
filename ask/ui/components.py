from typing import Self, Literal
from ask.ui.styles import Colors, Borders, ansi_len

Side = Literal['top', 'bottom', 'left', 'right']
Spacing = int | dict[Side, int]

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
    def __init__(self):
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
    def __init__(self, text: str, margin: Spacing = 0):
        super().__init__()
        self.text = text
        self.margin = margin

    def __getitem__(self, args: tuple['Component', ...]) -> Self:
        raise NotImplementedError("Text components cannot have children")

    def render(self) -> str:
        return add_margin(self.text, self.margin)


class Box(Component):
    def __init__(self, width=None, height=None, margin=None, padding=None, border_color=None, border_style=Borders.ROUND):
        self.width = width
        self.height = height
        self.margin = margin
        self.padding = padding
        self.border_style = border_style
        self.border_color = border_color

    def render(self):
        content = '\n'.join(child.render() for child in self.children)
        content = add_margin(content, self.padding)
        lines = content.split('\n')
        content_width = max(ansi_len(line) for line in lines)
        width = self.width if self.width else content_width
        height = self.height if self.height else len(lines)
        color_code = self.border_color or ''

        top_border = Colors.ansi(self.border_style["topLeft"] + self.border_style["top"] * width + self.border_style["topRight"], color_code)
        bottom_border = Colors.ansi(self.border_style["bottomLeft"] + self.border_style["bottom"] * width + self.border_style["bottomRight"], color_code)

        rendered_lines = [top_border]
        for i in range(height):
            if i < len(lines):
                line = lines[i]
            else:
                line = ''
            line_content = line + ' ' * (width - ansi_len(line))
            rendered_line = Colors.ansi(self.border_style['left'], color_code) + line_content + Colors.ansi(self.border_style['right'], color_code)
            rendered_lines.append(rendered_line)
        rendered_lines.append(bottom_border)
        rendered = '\n'.join(rendered_lines)
        return add_margin(rendered, self.margin)
