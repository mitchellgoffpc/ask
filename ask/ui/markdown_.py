import re
from io import StringIO
from typing import Any, cast
from markdown import Markdown, Extension
from markdown.blockprocessors import BlockProcessor
from markdown.util import AtomicString
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import TerminalFormatter, Terminal256Formatter, TerminalTrueColorFormatter
from pygments.util import ClassNotFound
from xml.etree.ElementTree import Element, SubElement

from ask.ui.styles import Colors, Styles, Theme, ANSI_256_SUPPORT, ANSI_16M_SUPPORT

def highlight_code(code: str, language: str) -> str:
    formatter: Any
    if ANSI_16M_SUPPORT:
        formatter = TerminalTrueColorFormatter()
    elif ANSI_256_SUPPORT:
        formatter = Terminal256Formatter()
    else:
        formatter = TerminalFormatter()

    try:
        lexer = get_lexer_by_name(language)
    except ClassNotFound:
        lexer = guess_lexer(code)
    return cast(str, highlight(code, lexer, formatter))


# Codeblock parsing extension

class FencedCodeExtension(Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(FencedCodeBlockProcessor(md.parser), 'fenced_code', 175)

class FencedCodeBlockProcessor(BlockProcessor):
    RE_FENCE_START = r'(?:^|\n)```(?P<lang>[\w#.+-]*) *(?=\n)'
    RE_FENCE_END = r'\n```$'

    def test(self, parent, block):
        return re.search(self.RE_FENCE_START, block)

    def run(self, parent, blocks):
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
                for _ in range(0, block_num + 1):
                    blocks.pop(0)
                return True

        return False


# ANSI rendering extension

class ANSIExtension(Extension):
    BLOCK_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'li', 'pre', 'blockquote'}
    HTML_TO_ANSI = {
        'strong': (Styles.BOLD, Styles.BOLD_END),
        'em': (Styles.ITALIC, Styles.ITALIC_END),
        'code': (Colors.HEX(Theme.BLUE), Colors.END),
        'li': ('• ', ''),
    } | {f'h{i}': (Styles.BOLD, Styles.BOLD_END) for i in range(1, 7)}

    def render_code_block(self, element: Element) -> str:
        language = element.attrib.get('language', '')
        code = element.text or ''

        return highlight_code(code, language) + (element.tail or "")

    def render_basic_element(self, element: Element, stream: StringIO, indent: int) -> None:
        start, end = self.HTML_TO_ANSI.get(element.tag, ('', ''))
        stream.write(start)
        if element.text and element.tag in self.BLOCK_TAGS:
            element.text = element.text.lstrip('\n')
        if element.text:
            stream.write(element.text)
            if len(element) and list(element)[0].tag in self.BLOCK_TAGS:
                stream.write('\n')

        prev_tag = None
        for sub in element:
            if prev_tag:
                if prev_tag == 'li' and sub.tag == 'li':
                    stream.write('\n')
                elif prev_tag in self.BLOCK_TAGS and sub.tag in self.BLOCK_TAGS :
                    stream.write('\n\n')
            self.render_element(sub, stream, indent)
            prev_tag = sub.tag

        stream.write(end)
        if element.tail:
            if element.tag in self.BLOCK_TAGS:
                element.tail = element.tail.rstrip('\n')
            stream.write(element.tail)

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

    def extendMarkdown(self, md):
        self.tab_length = md.tab_length
        md.serializer = self.render_root
        md.stripTopLevelTags = False
        md.set_output_format = lambda x: x


# Markdown renderer

md = Markdown(tab_length=2, extensions=[FencedCodeExtension(), ANSIExtension()])

def render_markdown(text: str) -> str:
    return md.convert(text)
