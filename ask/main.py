#!/usr/bin/env python3
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from ask.files import read_files
from ask.models import MODELS, MODEL_SHORTCUTS, Message, Text, Image, ToolRequest, ToolResponse
from ask.prompts import load_system_prompt
from ask.tools import TOOLS, Tool, ToolCallStatus
from ask.ui.app import App
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

    # Read any attached files
    files = asyncio.run(read_files(args.file))
    text_files = {fn: content for fn, content in files.items() if isinstance(content, Text)}
    image_files = {fn: content for fn, content in files.items() if isinstance(content, Image)}

    messages = {uuid4(): Message(role='user', content=content) for content in image_files.values()}
    if text_files:
        file_list = '\n'.join(f'- {fp}' for fp in text_files)
        messages[uuid4()] = Message(role='user', content=Text(f'Take a look at these files:\n{file_list}'))

        for file_path, data in text_files.items():
            call_id = str(uuid4())
            tool_args = {'file_path': str(Path(file_path).absolute().as_posix())}
            messages[uuid4()] = Message(role='assistant', content=ToolRequest(call_id=call_id, tool='Read', arguments=tool_args))
            messages[uuid4()] = Message(role='user', content=ToolResponse(call_id=call_id, tool='Read', response=data.text, status=ToolCallStatus.COMPLETED))

    if question:
        messages[uuid4()] = Message(role='user', content=Text(question))

    # Launch the UI
    model = MODEL_SHORTCUTS[args.model]
    tools: list[Tool] = list(TOOLS.values())
    asyncio.run(render_root(App(model=model, messages=messages, tools=tools, system_prompt=args.system)))


if __name__ == '__main__':
    main()
