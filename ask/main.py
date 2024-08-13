#!/usr/bin/env python3
import sys
import glob
import json
import argparse
import itertools
from pathlib import Path
from ask.chat import chat
from ask.query import query
from ask.models import MODELS, MODEL_SHORTCUTS, Prompt, Model
from ask.edit import EDIT_SYSTEM_PROMPT, UDIFF_SYSTEM_PROMPT, apply_edits

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
        for chunk in query(prompt, model, system_prompt=system_prompt):
            print(chunk, end='', flush=True)
            chunks.append(chunk)
    except KeyboardInterrupt:
        pass
    return ''.join(chunks)

def edit(prompt: Prompt, model: Model, system_prompt: str, diff: bool) -> None:
    default_system_prompt = UDIFF_SYSTEM_PROMPT if diff else EDIT_SYSTEM_PROMPT
    response = ask(prompt, model, system_prompt or default_system_prompt)
    apply_edits(response, diff)


# Entry point

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, default='sonnet', help="Model to use for the query")
    parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
    parser.add_argument('-e', '--edit', action='store_true', help="Edit mode")
    parser.add_argument('-d', '--diff', action='store_true', help="Diff mode using udiff patches")
    parser.add_argument('-s', '--system', type=str, default='', help="System prompt for the model")
    parser.add_argument('-j', '--json', action='store_true', help="Parse the input as json")
    parser.add_argument('-c', '--chat', action='store_true', help="Enable chat mode")
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
        file_paths = list(itertools.chain.from_iterable(glob.glob(fn) for fn in args.file))
        file_paths = list(itertools.chain.from_iterable(list_files(Path(fn)) for fn in file_paths))
        file_data = {path: path.read_text().strip() for path in file_paths}
        context.extend(f'{path}\n```\n{data}\n```' for path, data in file_data.items())
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
        assert not args.edit and not args.diff, "editing and diff not supported in chat mode"
        chat(prompt, model, args.system)
    elif args.edit or args.diff:
        edit(prompt, model, args.system, args.diff)
    else:
        ask(prompt, model, args.system)


if __name__ == '__main__':
    main()
