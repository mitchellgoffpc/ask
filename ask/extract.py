import re
from bs4 import BeautifulSoup, NavigableString, Tag, PageElement

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


if __name__ == "__main__":
    import sys
    import requests
    if len(sys.argv) != 2:
        print("Usage: python extract.py <path_to_html_file_or_url>")
        sys.exit(1)

    input_source = sys.argv[1]
    if input_source.startswith(('http://', 'https://')):
        response = requests.get(input_source)
        response.raise_for_status()
        html_content = response.text
    else:
        with open(input_source, 'r', encoding='utf-8') as f:
            html_content = f.read()

    body = extract_body(html_content)
    markdown = html_to_markdown(body)
    print(markdown)
