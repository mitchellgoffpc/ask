#!/usr/bin/env python3
import argparse
import asyncio
import sys
from uuid import uuid4

from ask.files import read_files
from ask.models import MODELS, MODEL_SHORTCUTS, Message, Text, Image
from ask.prompts import load_system_prompt
from ask.query import act
from ask.tools import TOOLS, Tool
from ask.ui.app import App
from ask.ui.render import render_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, default='sonnet', help="Model to use for the query")
    parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
    parser.add_argument('-s', '--system', type=str, default=load_system_prompt(), help="System prompt for the model")
    parser.add_argument('-p', '--print', action='store_true', help="Print response and exit")
    parser.add_argument('question', nargs=argparse.REMAINDER)
    parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    args = parser.parse_args()

    # Sanity checks
    if args.print and not args.question and sys.stdin.isatty():
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
    question = question.strip()

    # Read any attached files
    files = read_files(args.file)
    text_files = {fn: content for fn, content in files.items() if isinstance(content, Text)}
    if text_files:
        files_context = '\n\n'.join(f'### `{fn}`\n\n```\n{content.text}\n```' for fn, content in text_files.items())
        question = f"{files_context}\n\n{question}"

    model = MODEL_SHORTCUTS[args.model]
    tools: list[Tool] = list(TOOLS.values())

    # Launch the UI, or run the query and exit
    images = {uuid4(): content for content in files.values() if isinstance(content, Image)}
    messages = {uuid4(): Message(role='user', content={**images, uuid4(): Text(question)})} if question else {}
    if args.print:
        asyncio.run(act(model, list(messages.values()), tools, args.system))
    else:
        asyncio.run(render_root(App(model=model, messages=messages, tools=tools, system_prompt=args.system)))


if __name__ == '__main__':
    main()
