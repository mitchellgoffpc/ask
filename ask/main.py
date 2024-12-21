#!/usr/bin/env python3
import sys
import glob
import json
import argparse
import itertools
from pathlib import Path
from ask.chat import chat
from ask.edit import apply_edits
from ask.query import query_text, query_bytes
from ask.command import extract_command, execute_command
from ask.models import MODELS, MODEL_SHORTCUTS, Prompt, Model, TextModel, ImageModel

DEFAULT_SYSTEM_PROMPT = """
    Your task is to assist the user with whatever they ask of you.
    When asked to write or modifiy files, you should denote the file names in this format:\n\n### `path/to/file`\n\n```\nfile contents here\n```\n\n
    If a file is long and you want to leave some parts unchanged, add an [UNCHANGED] line to the edit to denote a section of code that shouldn't be changed.
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


# Act / Generate

def ask(prompt: Prompt, model: Model, system_prompt: str) -> str:
    chunks = []
    for chunk in query_text(prompt, model, system_prompt=system_prompt):
        print(chunk, end='', flush=True)
        chunks.append(chunk)
    print()
    return ''.join(chunks)

def act(prompt: Prompt, model: Model, system_prompt: str) -> None:
    try:
        while True:
            response = ask(prompt, model, system_prompt)
            apply_edits(response)
            command_type, command = extract_command(response)
            if command:
                result = execute_command(command_type, command)
                prompt.append({"role": "assistant", "content": response})
                prompt.append({"role": "user", "content": f"Command output:\n{result}"})
            else:
                break
    except KeyboardInterrupt:
        print('\n')

def generate(prompt: Prompt, model: Model, system_prompt: str) -> None:
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
    context: list[str] = []
    if args.file:
        file_names = list(itertools.chain.from_iterable(safe_glob(fn) for fn in args.file))
        file_paths = list(itertools.chain.from_iterable(list_files(Path(fn)) for fn in file_names))
        file_data = {path: path.read_text().strip() for path in file_paths}
        context.extend(f'### `{path}`\n\n```\n{data}\n```' for path, data in file_data.items())
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
        chat(prompt, model, args.system)
    elif isinstance(model, ImageModel):
        generate(prompt, model, args.system)
    elif isinstance(model, TextModel):
        act(prompt, model, args.system)


if __name__ == '__main__':
    main()
