#!/usr/bin/env python3
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4

from ask.commands import DocsCommand, FilesCommand, ModelCommand
from ask.config import CONFIG_DIR, HISTORY_PATH, Config
from ask.messages import Message, SystemPrompt, ToolDescriptor
from ask.models import MODEL_SHORTCUTS, MODELS
from ask.prompts import get_agents_md_path, load_system_prompt
from ask.tools import TOOLS
from ask.tools.read import read_file
from ask.tree import MessageTree
from ask.ui.app import App
from ask.ui.core import render_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, default=Config['default_model'], help="Model to use for the query")
    parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
    parser.add_argument('-s', '--system', type=str, default=load_system_prompt(), help="System prompt for the model")
    parser.add_argument('-r', '--resume', type=UUID, help="Resume from root UUID")
    parser.add_argument('question', nargs=argparse.REMAINDER)
    parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    args = parser.parse_args()

    # Sanity checks
    if args.model not in MODEL_SHORTCUTS:
        sys.stderr.write(f"Invalid model {args.model!r}. Valid options are:\n")
        max_name_length = max(len(model.name) for model in MODELS)
        max_shortcuts_length = max(len(', '.join(model.shortcuts)) for model in MODELS)
        format_string = f"  {{:<{max_name_length}}}  {{:<{max_shortcuts_length}}}"
        for model in MODELS:
            sys.stderr.write(format_string.format(model.name, ', '.join(model.shortcuts)) + "\n")
        sys.stderr.write("\nUse any model name or shortcut from the list above.\n")
        sys.exit(1)

    if args.resume:
        history_file = HISTORY_PATH / f"{args.resume}.json"
        if not history_file.is_file():
            sys.stderr.write(f"History file not found for root {args.resume}\n")
            sys.exit(1)
        tree, head = MessageTree.load(history_file.read_text())
        messages = dict(tree.items(head))
    else:
        # Add system and tool descriptor messages
        messages: dict[UUID, Message] = {}
        messages[uuid4()] = Message(role='user', content=ModelCommand(command='', model=MODEL_SHORTCUTS[args.model].name))
        messages[uuid4()] = Message(role='user', content=SystemPrompt(text=args.system))
        for tool in TOOLS.values():
            messages[uuid4()] = Message(role='user', content=ToolDescriptor(name=tool.name, description=tool.description, input_schema=tool.get_input_schema()))

        # Attach USER.md / AGENTS.md files
        if (user_file := CONFIG_DIR / 'USER.md').exists():
            messages[uuid4()] = Message(role='user', content=DocsCommand(prompt_key='user', file_path=user_file, file_contents=user_file.read_text()))
        if agents_file := get_agents_md_path():
            messages[uuid4()] = Message(role='user', content=DocsCommand(prompt_key='agents', file_path=agents_file, file_contents=agents_file.read_text()))

    # Read any attached files
    if args.file:
        file_contents = {Path(fn): read_file(Path(fn)) for fn in args.file}
        messages[uuid4()] = Message(role='user', content=FilesCommand(file_contents=file_contents))

    # Read from stdin
    question = ' '.join(args.question)
    if not sys.stdin.isatty():
        stdin = parser.parse_args().stdin.read()
        question = f'{stdin}\n\n{question}' if question else stdin
    question = question.strip()

    # Launch the UI
    asyncio.run(render_root(App(messages=messages, query=question)))


if __name__ == '__main__':
    main()
