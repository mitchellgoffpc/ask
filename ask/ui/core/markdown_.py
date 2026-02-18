import html
import re
from collections.abc import Callable
from functools import cache
from io import StringIO
from typing import Any, cast
from xml.etree.ElementTree import Element, SubElement

from markdown import Extension, Markdown
from markdown.blockprocessors import BlockProcessor
from markdown.util import AtomicString
from pygments import highlight
from pygments.formatters import Terminal256Formatter, TerminalFormatter, TerminalTrueColorFormatter
from pygments.lexer import Lexer
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, guess_lexer
from pygments.util import ClassNotFound

from ask.ui.core.styles import ANSI_16M_SUPPORT, ANSI_256_SUPPORT, Colors, Styles


def highlight_code(code: str, *, language: str = '', file_path: str = '') -> str:
    formatter: Any
    if ANSI_16M_SUPPORT:
        formatter = TerminalTrueColorFormatter()
    elif ANSI_256_SUPPORT:
        formatter = Terminal256Formatter()
    else:
        formatter = TerminalFormatter()

    lexer = None
    lexer_fns: list[tuple[Callable[[str], Lexer], str]] = [(get_lexer_by_name, language), (get_lexer_for_filename, file_path), (guess_lexer, code)]
    for get_lexer, arg in lexer_fns:
        if arg:
            try:
                lexer = get_lexer(arg)
                break
            except ClassNotFound:
                pass
    return cast(str, highlight(code, lexer, formatter)) if lexer else code


# Codeblock parsing extension

class FencedCodeExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.parser.blockprocessors.register(FencedCodeBlockProcessor(md.parser), 'fenced_code', 175)

class FencedCodeBlockProcessor(BlockProcessor):
    RE_FENCE_START = r'(?:^|\n)```(?P<lang>[\w#.+-]*) *(?=\n)'
    RE_FENCE_END = r'\n```$'

    def test(self, parent: Element, block: str) -> bool:
        return bool(re.search(self.RE_FENCE_START, block))

    def run(self, parent: Element, blocks: list[str]) -> bool:
        match = re.search(self.RE_FENCE_START, blocks[0])
        assert match is not None

        # Handle text before code fence if it exists
        fence_start = match.start()
        if fence_start > 0:
            self.parser.parseBlocks(parent, [blocks[0][:fence_start]])

        # Find block with ending fence
        for block_num, block in enumerate(blocks):
            if re.search(self.RE_FENCE_END, block):
                blocks[0] = blocks[0][fence_start + len(match.group()):]
                blocks[block_num] = re.sub(self.RE_FENCE_END, '', blocks[block_num])
                e = SubElement(parent, 'pre')
                e.set('language', match.group('lang'))
                e.text = AtomicString('\n\n'.join(blocks[: block_num + 1]))
                for _ in range(block_num + 1):
                    blocks.pop(0)
                return True

        return False


# ANSI rendering extension

class ANSIExtension(Extension):
    BLOCK_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'li', 'pre', 'blockquote'}
    HTML_TO_ANSI = {
        'strong': (Styles.BOLD, Styles.BOLD_END),
        'em': (Styles.ITALIC, Styles.ITALIC_END),
        'li': ('• ', ''),
    } | {f'h{i}': (Styles.BOLD, Styles.BOLD_END) for i in range(1, 7)}

    def __init__(self, *, code_color: str | None = None) -> None:
        super().__init__()
        if code_color:
            self.HTML_TO_ANSI = self.HTML_TO_ANSI | {'code': (Colors.HEX(code_color), Colors.END)}

    def render_code_block(self, element: Element) -> str:
        language = element.attrib.get('language', '')
        code = element.text or ''
        return highlight_code(code, language=language) + (element.tail or "")

    def render_basic_element(self, element: Element, stream: StringIO, indent: int) -> None:
        start, end = self.HTML_TO_ANSI.get(element.tag, ('', ''))
        stream.write(start)
        if element.text and element.tag in self.BLOCK_TAGS:
            element.text = element.text.lstrip('\n')
        if element.text:
            stream.write(html.unescape(element.text))
            if len(element) and list(element)[0].tag in self.BLOCK_TAGS:
                stream.write('\n')

        prev_tag = None
        for sub in element:
            if prev_tag:
                if (sub.tag == 'li' and (prev_tag == 'li' or prev_tag not in self.BLOCK_TAGS)) or \
                   (sub.tag in ('ul', 'ol') and element.tag == 'li'):
                    stream.write('\n')
                elif sub.tag in self.BLOCK_TAGS:
                    stream.write('\n\n')
            self.render_element(sub, stream, indent)
            prev_tag = sub.tag

        stream.write(end)
        if element.tail:
            if element.tag in self.BLOCK_TAGS:
                element.tail = element.tail.rstrip('\n')
            stream.write(html.unescape(element.tail))

    def render_element(self, element: Element, stream: StringIO, indent: int) -> None:
        if element.tag == "pre":
            stream.write(self.render_code_block(element).rstrip('\n'))
            if element.tail:
                stream.write(element.tail.rstrip('\n'))
        elif element.tag in ("ul", "ol"):
            liststream = StringIO()
            self.render_basic_element(element, liststream, indent + 1)
            lines = liststream.getvalue().splitlines(keepends=True)
            result = ''.join(' ' * self.tab_length * min(1, indent) + line if line.strip() else line for line in lines)
            stream.write(result)
        else:
            self.render_basic_element(element, stream, indent)

    def render_root(self, element: Element) -> str:
        stream = StringIO()
        self.render_element(element, stream, indent=0)
        return stream.getvalue()

    def extendMarkdown(self, md: Markdown) -> None:
        self.tab_length = md.tab_length
        md.serializer = self.render_root
        md.stripTopLevelTags = False
        md.set_output_format = lambda x: x  # type: ignore[invalid-assignment]


# Markdown renderer

@cache
def markdown(code_color: str | None = None) -> Markdown:
    return Markdown(tab_length=2, extensions=[FencedCodeExtension(), ANSIExtension(code_color=code_color)])

def render_markdown(text: str, code_color: str | None = None) -> str:
    return markdown(code_color=code_color).convert(text)
