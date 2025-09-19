#!/usr/bin/env python3
import argparse
import asyncio
import re
import sys
from pathlib import Path
from uuid import uuid4

from ask.models import MODELS, MODEL_SHORTCUTS, Message, Text
from ask.prompts import load_system_prompt
from ask.tools import TOOLS, Tool
from ask.tools.read import read_file
from ask.ui.app import App
from ask.ui.commands import FilesCommand, DocsCommand
from ask.ui.render import render_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, default='sonnet', help="Model to use for the query")
    parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
    parser.add_argument('-s', '--system', type=str, default=load_system_prompt(), help="System prompt for the model")
    parser.add_argument('question', nargs=argparse.REMAINDER)
    parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    args = parser.parse_args()

    # Sanity checks
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

    # Read any AGENTS.md files from current directory up to root
    messages = {}
    for parent in (Path.cwd(), *Path.cwd().parents):
        agents_file = parent / "AGENTS.md"
        if agents_file.exists():
            messages[uuid4()] = Message(role='user', content=DocsCommand(command='', file_path=agents_file, file_contents=agents_file.read_text()))

    # Read any attached files
    attached_files = args.file + [Path(m[1:]) for m in re.findall(r'@\S+', question) if Path(m[1:]).is_file()]
    if attached_files:
        prompt = question or f'Read {len(attached_files)} files'
        file_contents = {Path(fn): read_file(Path(fn)) for fn in attached_files}
        messages[uuid4()] = Message(role='user', content=FilesCommand(command=prompt, file_contents=file_contents))
    elif question:
        messages[uuid4()] = Message(role='user', content=Text(question))

    # Launch the UI
    model = MODEL_SHORTCUTS[args.model]
    tools: list[Tool] = list(TOOLS.values())
    asyncio.run(render_root(App(model=model, messages=messages, tools=tools, system_prompt=args.system)))


if __name__ == '__main__':
    main()
