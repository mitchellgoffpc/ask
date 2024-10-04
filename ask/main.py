#!/usr/bin/env python3
import sys
import glob
import json
import argparse
import itertools
from pathlib import Path
from ask.chat import chat
from ask.query import query_text, query_bytes
from ask.models import MODELS, MODEL_SHORTCUTS, Prompt, Model, TextModel, ImageModel
from ask.edit import EDIT_SYSTEM_PROMPT, apply_edits

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


# Ask / Edit

def ask(prompt: Prompt, model: Model, system_prompt: str) -> str:
    chunks = []
    try:
        for chunk in query_text(prompt, model, system_prompt=system_prompt):
            print(chunk, end='', flush=True)
            chunks.append(chunk)
    except KeyboardInterrupt:
        print('\n')
    return ''.join(chunks)

def generate(prompt: Prompt, model: Model, system_prompt: str) -> None:
    try:
        data = b''.join(query_bytes(prompt, model, system_prompt=system_prompt))
        with open('/tmp/image.jpg', 'wb') as f:
            f.write(data)
        print("Image saved to /tmp/image.jpg")
    except KeyboardInterrupt:
        pass

def edit(prompt: Prompt, model: Model, system_prompt: str) -> None:
    response = ask(prompt, model, system_prompt or EDIT_SYSTEM_PROMPT)
    apply_edits(response)


# Entry point

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, default='sonnet', help="Model to use for the query")
    parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
    parser.add_argument('-e', '--edit', action='store_true', help="Edit mode")
    parser.add_argument('-s', '--system', type=str, default='', help="System prompt for the model")
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
    context: list[str] = []
    if args.file:
        file_names = list(itertools.chain.from_iterable(safe_glob(fn) for fn in args.file))
        file_paths = list(itertools.chain.from_iterable(list_files(Path(fn)) for fn in file_names))
        file_data = {path: path.read_text().strip() for path in file_paths}
        context.extend(f'<file name="{path}">\n{data}\n</file>' for path, data in file_data.items())
    if context:
        context_str = '\n\n'.join(context)
        question = f"{context_str}\n\n{question}"

    # Parse json data
    if args.json:
        assert not args.file, "files not supported in JSON mode"
        prompt = json.loads(question)
    else:
        prompt = [{'role': 'user', 'content': question}]

    # Run the query
    model = MODEL_SHORTCUTS[args.model]
    if args.chat:
        assert not args.edit, "editing not supported in chat mode"
        chat(prompt, model, args.system)
    elif args.edit:
        edit(prompt, model, args.system)
    elif isinstance(model, ImageModel):
        generate(prompt, model, args.system)
    elif isinstance(model, TextModel):
        ask(prompt, model, args.system)


if __name__ == '__main__':
    main()
