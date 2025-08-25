import aiohttp
import glob
import itertools
import re
import sys
from bs4 import BeautifulSoup, NavigableString, Tag, PageElement
from pathlib import Path

from ask.models import Text, Image

IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}

# File helpers

def safe_glob(fn: str) -> list[str]:
    result = glob.glob(fn)
    if not result:
        raise FileNotFoundError(fn)
    return result

def list_files(path: Path) -> list[Path]:
    if path.name.startswith('.'):
        return []
    elif path.is_file():
        return [path]
    elif path.is_dir():
        return list(itertools.chain.from_iterable(list_files(child) for child in path.iterdir()))
    else:
        raise RuntimeError("Unknown file type")

async def process_url(url: str) -> tuple[str, str | bytes]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            mimetype = response.headers.get('Content-Type', ';').split(';')[0]

            if mimetype.startswith('text/html'):
                text = await response.text()
                body = extract_body(text)
                content = html_to_markdown(body)
                return 'text/markdown', content
            elif mimetype.startswith('image/'):
                content = (await response.read()).decode('utf-8')
                return mimetype, content
            elif mimetype.startswith('text/') or mimetype == 'application/json':
                text = await response.text()
                return mimetype, text.strip()
            else:
                raise ValueError(f"Unsupported content type {mimetype} for URL {url}")

async def read_files(files: list[str]) -> dict[str, Text | Image]:
    image_files: dict[str, Image] = {}
    text_files: dict[str, Text] = {}

    for fn in files:
        if fn.startswith(('http://', 'https://')):
            try:
                mimetype, content = await process_url(fn)
                if mimetype.startswith('image/'):
                    image_files[fn] = Image(mimetype, content)  # type: ignore
                else:
                    text_files[fn] = Text(content)  # type: ignore
            except Exception as e:
                print(f"Error processing URL {fn}: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            try:
                file_names = safe_glob(fn)
                file_paths = list(itertools.chain.from_iterable(list_files(Path(name)) for name in file_names))
                for path in file_paths:
                    if path.suffix in IMAGE_TYPES:
                        mimetype = IMAGE_TYPES[path.suffix]
                        image_files[str(path)] = Image(mimetype, path.read_bytes())
                    else:
                        text_files[str(path)] = Text(path.read_text().strip())
            except FileNotFoundError:
                print(f"{fn}: No such file or directory", file=sys.stderr)
                sys.exit(1)
            except PermissionError:
                print(f"{fn}: Permission denied", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error processing file {fn}: {e}", file=sys.stderr)
                sys.exit(1)

    return text_files | image_files


# HTML to Markdown conversion

def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    markdown = convert_element(soup).strip()
    return re.sub(r'\n{3,}', '\n\n', markdown)

def convert_element(element: PageElement) -> str:
    if isinstance(element, NavigableString):
        return str(element)
    elif isinstance(element, Tag):
        markdown = ''
        if element.name == 'a' and element.get_text(strip=True) == '¶':
            return ''
        elif element.name in ['b', 'strong']:
            content = ''.join(convert_element(child) for child in element.contents)
            markdown += f'**{content}**'
        elif element.name in ['i', 'em']:
            content = ''.join(convert_element(child) for child in element.contents)
            markdown += f'*{content}*'
        elif element.name == 'li':
            content = ''.join(convert_element(child) for child in element.contents)
            markdown += f'- {content}\n'
        elif element.name in ['ul', 'ol']:
            for child in element.contents:
                markdown += convert_element(child)
        elif element.name == 'p':
            content = ''.join(convert_element(child) for child in element.contents)
            markdown += f'{content}\n\n'
        elif element.name == 'br':
            markdown += '\n'
        elif element.name == 'div':
            content = ''.join(convert_element(child) for child in element.contents)
            markdown += f'\n{content.strip()}\n'
        else:
            for child in element.contents:
                markdown += convert_element(child)
        return markdown
    else:
        return ''

def extract_body(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['nav', 'style', 'script', 'img']):
        tag.decompose()
    current_element = soup.body if soup.body else soup

    while True:
        children = [child for child in current_element.contents if isinstance(child, Tag)]
        if not children:
            break
        child_text_lengths = [(child, len(child.get_text(strip=True))) for child in children]
        total_length = sum(length for _, length in child_text_lengths)
        if total_length == 0:
            break
        max_child, max_length = max(child_text_lengths, key=lambda x: x[1])
        other_children_lengths = sum(length for child, length in child_text_lengths if child != max_child)
        other_children = [child for child, _ in child_text_lengths if child != max_child]
        if all(child.find(re.compile('^h[1-6]$')) for child in other_children):
            break
        if max_length / total_length < 0.5 or max_length <= other_children_lengths * 10:
            break
        current_element = max_child

    return str(current_element)


# Entry point for testing

if __name__ == "__main__":
    import asyncio
    import sys

    async def main():
        if len(sys.argv) != 2:
            print("Usage: python extract.py <path_to_html_file_or_url>")
            sys.exit(1)

        input_source = sys.argv[1]
        if input_source.startswith(('http://', 'https://')):
            async with aiohttp.ClientSession() as session:
                async with session.get(input_source) as response:
                    response.raise_for_status()
                    html_content = await response.text()
        else:
            with open(input_source, 'r', encoding='utf-8') as f:
                html_content = f.read()

        body = extract_body(html_content)
        markdown = html_to_markdown(body)
        print(markdown)

    asyncio.run(main())
