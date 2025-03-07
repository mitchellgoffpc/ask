from ask.ui.styles import Colors

class Borders:
    SINGLE = {
        "topLeft": "┌",
        "top": "─",
        "topRight": "┐",
        "right": "│",
        "bottomRight": "┘",
        "bottom": "─",
        "bottomLeft": "└",
        "left": "│"
    }

    DOUBLE = {
        "topLeft": "╔",
        "top": "═",
        "topRight": "╗",
        "right": "║",
        "bottomRight": "╝",
        "bottom": "═",
        "bottomLeft": "╚",
        "left": "║"
    }

    ROUND = {
        "topLeft": "╭",
        "top": "─",
        "topRight": "╮",
        "right": "│",
        "bottomRight": "╯",
        "bottom": "─",
        "bottomLeft": "╰",
        "left": "│"
    }

    BOLD = {
        "topLeft": "┏",
        "top": "━",
        "topRight": "┓",
        "right": "┃",
        "bottomRight": "┛",
        "bottom": "━",
        "bottomLeft": "┗",
        "left": "┃"
    }

    SINGLE_DOUBLE = {
        "topLeft": "╓",
        "top": "─",
        "topRight": "╖",
        "right": "║",
        "bottomRight": "╜",
        "bottom": "─",
        "bottomLeft": "╙",
        "left": "║"
    }

    DOUBLE_SINGLE = {
        "topLeft": "╒",
        "top": "═",
        "topRight": "╕",
        "right": "│",
        "bottomRight": "╛",
        "bottom": "═",
        "bottomLeft": "╘",
        "left": "│"
    }

    CLASSIC = {
        "topLeft": "+",
        "top": "-",
        "topRight": "+",
        "right": "|",
        "bottomRight": "+",
        "bottom": "-",
        "bottomLeft": "+",
        "left": "|"
    }


class Box:
    def __init__(self, text, width=None, height=None, border_color=None, border_style=Borders.ROUND):
        self.text = text
        self.width = width
        self.height = height
        self.border_style = border_style
        self.border_color = border_color

    def render(self):
        lines = self.text.split('\n')
        content_width = max(len(line) for line in lines)
        width = self.width if self.width else content_width
        height = self.height if self.height else len(lines)
        color_code = Colors.hex(self.border_color) if self.border_color else ''

        top_border = color_code + self.border_style["topLeft"] + self.border_style["top"] * width + self.border_style["topRight"] + Colors.END
        bottom_border = color_code + self.border_style["bottomLeft"] + self.border_style["bottom"] * width + self.border_style["bottomRight"] + Colors.END

        rendered_lines = [top_border]
        for i in range(height):
            if i < len(lines):
                line = lines[i]
            else:
                line = ''
            line_content = line.ljust(width)
            rendered_line = f"{color_code}{self.border_style['left']}{Colors.END}{line_content}{color_code}{self.border_style['right']}{Colors.END}"
            rendered_lines.append(rendered_line)
        rendered_lines.append(bottom_border)
        return '\n'.join(rendered_lines)
