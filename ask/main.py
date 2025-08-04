#!/usr/bin/env python3
import sys
import argparse
from ask.tools import Tool
from ask.query import act
from ask.models import MODELS, MODEL_SHORTCUTS, Message, Text, Image
from ask.files import read_files
from ask.ui.app import App
from ask.ui.render import render_root

DEFAULT_SYSTEM_PROMPT = """
    Your task is to assist the user with whatever they ask of you.
    When asked to write or modifiy files, you should denote the file names in this format:\n\n### `path/to/file`\n\n```\nfile contents here\n```\n\n
    If a file is long and you want to leave some parts unchanged,
    add a line that with an [UNCHANGED] marker to denote a section of code that shouldn't be changed.
    The line should just say '[UNCHANGED]', with no comment markers or additional text.
    You should never write 'previous code goes here' or 'original code unchanged', always use the [UNCHANGED] marker instead.\n
    Be sure to include some surrounding context in each section so I know where it's supposed to go.
    Write clean code, and avoid leaving comments explaining what you did.
""".replace('\n    ', ' ').replace('\n ', '\n').strip()  # dedent and strip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', type=str, default='sonnet', help="Model to use for the query")
    parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
    parser.add_argument('-s', '--system', type=str, default=DEFAULT_SYSTEM_PROMPT, help="System prompt for the model")
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
    tools: list[Tool] = []  # list(TOOLS.values())

    # Launch the UI, or run the query and exit
    images = [content for content in files.values() if isinstance(content, Image)]
    messages = [Message(role='user', content=[*images, Text(question)])]
    if args.print:
        act(model, messages, tools, args.system)
    else:
        render_root(App())


if __name__ == '__main__':
    main()
