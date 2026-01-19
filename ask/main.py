#!/usr/bin/env python3
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from ask.commands import FilesCommand, DocsCommand
from ask.messages import Message
from ask.models import MODELS, MODEL_SHORTCUTS
from ask.prompts import load_system_prompt, get_agents_md_path
from ask.tools import TOOLS, Tool
from ask.tools.read import read_file
from ask.ui.app import App
from ask.ui.config import CONFIG_DIR, Config
from ask.ui.core.render import render_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, default=Config['default_model'], help="Model to use for the query")
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

    # Attach USER.md / AGENTS.md files
    messages = {}
    if (user_file := CONFIG_DIR / 'USER.md').exists():
        messages[uuid4()] = Message(role='user', content=DocsCommand(prompt_key='user', file_path=user_file, file_contents=user_file.read_text()))
    if agents_file := get_agents_md_path():
        messages[uuid4()] = Message(role='user', content=DocsCommand(prompt_key='agents', file_path=agents_file, file_contents=agents_file.read_text()))

    # Read any attached files
    if args.file:
        file_contents = {Path(fn): read_file(Path(fn)) for fn in args.file}
        messages[uuid4()] = Message(role='user', content=FilesCommand(file_contents=file_contents))

    # Launch the UI
    model = MODEL_SHORTCUTS[args.model]
    tools: list[Tool] = list(TOOLS.values())
    asyncio.run(render_root(App(model=model, messages=messages, query=question, tools=tools, system_prompt=args.system)))


if __name__ == '__main__':
    main()
