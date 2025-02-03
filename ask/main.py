#!/usr/bin/env python3
import sys
import glob
import json
import argparse
import itertools
from pathlib import Path
import requests
from ask.chat import chat
from ask.edit import apply_edits
from ask.query import query_text, query_bytes
from ask.command import extract_command, execute_command
from ask.models import MODELS, MODEL_SHORTCUTS, Text, Image, Message, Model, TextModel, ImageModel
from ask.extract import extract_body, html_to_markdown

IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
DEFAULT_SYSTEM_PROMPT = """
    Your task is to assist the user with whatever they ask of you.
    When asked to write or modifiy files, you should denote the file names in this format:\n\n### `path/to/file`\n\n```\nfile contents here\n```\n\n
    If a file is long and you want to leave some parts unchanged, add a line that with an [UNCHANGED] marker to denote a section of code that shouldn't be changed.
    The line should just say '[UNCHANGED]', with no comment markers or additional text.
    You should never write 'previous code goes here' or 'original code unchanged', always use the [UNCHANGED] marker instead.\n
    Be sure to include some surrounding context in each section so I know where it's supposed to go.
    Write clean code, and avoid leaving comments explaining what you did.\n\n
    If you want to execute code on the user's system, respond with a command in the following format:\n\n### EXECUTE\n\n```bash\ncommand here\n```\n\n
    For platform-specific commands, use ### EXECUTE (linux/mac/windows). For example, a command that only works on Linux and macOS should be written as ### EXECUTE (linux/mac).\n\n
    For anonymous code snippets, use the following format:\n\n### CODE\n\n```language\nyour code here\n```
""".replace('\n    ', ' ').replace('\n ', '\n').strip()  # dedent and strip

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

def process_url(url: str) -> tuple[str, str | bytes]:
    response = requests.get(url)
    response.raise_for_status()
    mimetype = response.headers.get('Content-Type', ';').split(';')[0]

    if mimetype.startswith('text/html'):
        body = extract_body(response.text)
        content = html_to_markdown(body)
        return 'text/markdown', content
    elif mimetype.startswith('image/'):
        return mimetype, response.content
    elif mimetype.startswith('text/') or mimetype == 'application/json':
        return mimetype, response.text.strip()
    else:
        raise ValueError(f"Unsupported content type {mimetype} for URL {url}")

# Act / Generate

def ask(prompt: list[Message], model: Model, system_prompt: str) -> str:
    chunks = []
    for chunk in query_text(prompt, model, system_prompt=system_prompt):
        print(chunk, end='', flush=True)
        chunks.append(chunk)
    print()
    return ''.join(chunks)

def act(prompt: list[Message], model: Model, system_prompt: str) -> None:
    try:
        while True:
            response = ask(prompt, model, system_prompt)
            apply_edits(response)
            command_type, command = extract_command(response)
            if command:
                result = execute_command(command_type, command)
                prompt.append(Message(role="assistant", content=[Text(response)]))
                prompt.append(Message(role="user", content=[Text(f"I ran the command `{command}`. Here's the output I got:\n\n```\n{result}\n```")]))
            else:
                break
    except KeyboardInterrupt:
        print('\n')

def generate(prompt: list[Message], model: Model, system_prompt: str) -> None:
    try:
        data = b''.join(query_bytes(prompt, model, system_prompt=system_prompt))
        with open('/tmp/image.jpg', 'wb') as f:
            f.write(data)
        print("Image saved to /tmp/image.jpg")
    except KeyboardInterrupt:
        pass


# Entry point

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, default='sonnet', help="Model to use for the query")
    parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
    parser.add_argument('-s', '--system', type=str, default=DEFAULT_SYSTEM_PROMPT, help="System prompt for the model")
    parser.add_argument('-j', '--json', action='store_true', help="Parse the input as json")
    parser.add_argument('-c', '--chat', action='store_true', help="Enable chat mode")
    parser.add_argument('-r', '--repl', action='store_true', help="Enable repl mode")
    parser.add_argument('question', nargs=argparse.REMAINDER)
    parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    args = parser.parse_args()

    # Sanity checks
    if not args.chat and not args.question and sys.stdin.isatty():
        print('usage: ask <question>', file=sys.stderr)
        sys.exit(1)
    if args.model not in MODEL_SHORTCUTS:
        print(f"Invalid model {args.model!r}. Valid options are:", file=sys.stderr)
        max_name_length = max(len(model.name) for model in MODELS)
        max_shortcuts_length = max(len(', '.join(model.shortcuts)) for model in MODELS)
        format_string = f"  {{:<{max_name_length}}}  {{:<{max_shortcuts_length}}}"
        for model in MODELS:
            print(format_string.format(model.name, ', '.join(model.shortcuts)), file=sys.stderr)
        print("\nUse any model name or shortcut from the list above.", file=sys.stderr)
        sys.exit(1)

    # Read from stdin
    question = ' '.join(args.question)
    if not sys.stdin.isatty():
        stdin = parser.parse_args().stdin.read()
        question = f'{stdin}\n\n{question}' if question else stdin

    # Add file context
    question = question.strip()
    media_files: list[tuple[str, bytes]] = []
    text_files: list[tuple[str, str]] = []
    if args.file:
        for fn in args.file:
            if fn.startswith(('http://', 'https://')):
                try:
                    mimetype, content = process_url(fn)
                    if mimetype.startswith('image/'):
                        media_files.append((mimetype, content))  # type: ignore
                    else:
                        text_files.append((fn, content))  # type: ignore
                except Exception as e:
                    print(f"Error processing URL {fn}: {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                try:
                    file_names = safe_glob(fn)
                    file_paths = list(itertools.chain.from_iterable(list_files(Path(name)) for name in file_names))
                    for path in file_paths:
                        if path.suffix in IMAGE_TYPES:
                            media_files.append((IMAGE_TYPES[path.suffix], path.read_bytes()))
                        else:
                            text_files.append((str(path), path.read_text().strip()))
                except Exception as e:
                    print(f"Error processing file {fn}: {e}", file=sys.stderr)
                    sys.exit(1)

    # Render the request
    if text_files:
        context = '\n\n'.join(f'### `{fn}`\n\n```\n{text_content}\n```' for fn, text_content in text_files)
        question = f"{context}\n\n{question}"

    model = MODEL_SHORTCUTS[args.model]
    if args.json:
        assert not args.file, "files not supported in JSON mode"
        prompt = [Message(role=msg['role'], content=msg['content']) for msg in json.loads(question)]
    else:
        prompt = [Message(role='user', content=[Image(mimetype, data) for mimetype, data in media_files] + [Text(question)])]

    # Run the query
    if args.chat:
        chat(prompt, model, args.system)
    elif isinstance(model, ImageModel):
        generate(prompt, model, args.system)
    elif isinstance(model, TextModel):
        act(prompt, model, args.system)


if __name__ == '__main__':
    main()
