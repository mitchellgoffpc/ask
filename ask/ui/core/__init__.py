from typing import TypeAlias

from ask.ui.core.components import ElementTree, Component, Element, Text, Box, Widget, Controller
from ask.ui.core.markdown_ import render_markdown, highlight_code
from ask.ui.core.render import render_root
from ask.ui.core.styles import Axis, Borders, Colors, Styles, Theme, ansi_len, ansi_slice, wrap_lines
from ask.ui.core.textbox import TextBox

class UI:
    Component: TypeAlias = Component
    Element: TypeAlias = Element
    Text: TypeAlias = Text
    Box: TypeAlias = Box
    Widget: TypeAlias = Widget
    Controller: TypeAlias = Controller
    TextBox: TypeAlias = TextBox

__all__ = [
    'UI', 'ElementTree', 'Component', 'Element', 'Text', 'Box', 'Widget', 'Controller', 'TextBox',
    'Axis', 'Borders', 'Colors', 'Styles', 'Theme', 'ansi_len', 'ansi_slice', 'wrap_lines',
    'render_markdown', 'highlight_code',
    'render_root',
]
