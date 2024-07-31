#!/usr/bin/env python3
import sys
import glob
import json
import readline  # noqa: F401
import argparse
import itertools
from pathlib import Path
from ask.query import query
from ask.models import MODELS, Prompt, Model
from ask.edit import EDIT_SYSTEM_PROMPT, UDIFF_SYSTEM_PROMPT, print_diff, apply_udiff_edit, apply_section_edit, extract_code_block

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}

def list_files(path: Path) -> list[Path]:
    if path.name.startswith('.'):
        return []
    elif path.is_file():
        return [path]
    elif path.is_dir():
        return list(itertools.chain.from_iterable(list_files(child) for child in path.iterdir()))
    else:
        raise RuntimeError("Unknown file type")


# Ask / Output / Edit / Chat

def ask(prompt: Prompt, model: Model, system_prompt: str):
    try:
        chunks = []
        for chunk in query(prompt, model, system_prompt=system_prompt):
            print(chunk, end='', flush=True)
            chunks.append(chunk)
        return ''.join(chunks)
    except KeyboardInterrupt:
        return []

def output(prompt: Prompt, model: Model, system_prompt: str, file_path: Path):
    response = ask(prompt, model, system_prompt)
    response = extract_code_block(response)
    print_diff('', response, file_path)

    user_input = input(f"\nDo you want to save this to {file_path}? (y/n): ").strip().lower()
    if user_input == 'y':
        with open(file_path, 'w') as f:
            f.write(response)
        print(f"Saved output to {file_path}")

def edit(prompt: Prompt, model: Model, system_prompt: str, file_path: Path, diff: bool):
    file_data = file_path.read_text()
    default_system_prompt = UDIFF_SYSTEM_PROMPT if diff else EDIT_SYSTEM_PROMPT
    response = ask(prompt, model, system_prompt or default_system_prompt)
    modified = apply_udiff_edit(file_data, response) if diff else apply_section_edit(file_data, response)
    print_diff(file_data, modified, file_path)

    user_input = input(f"Do you want to apply this edit to {file_path}? (y/n): ").strip().lower()
    if user_input == 'y':
        with open(file_path, 'w') as f:
            f.write(modified)
        print(f"Saved edits to {file_path}")

def chat(prompt: Prompt, model: Model, system_prompt: str):
    prompt = [msg for msg in prompt if msg['content']]
    while True:
        try:
            user_input = input("> ")
            cmd = user_input.lower().strip()
            cmd = cmd.split()[0] if cmd else ''
            if cmd in ('exit', 'quit', '.exit', '.quit', ':exit', ':quit', ':q'):
                return
            elif cmd in ('.models', ':models'):
                print("Available models:")
                for m in MODELS:
                    print(f"- {m.name} ({', '.join(m.shortcuts)})")
            elif cmd in ('.model', ':model', ':m'):
                model_name = user_input[len(cmd + ' '):].strip()
                if not model_name:
                    print(f"Current model is {model.name}.")
                elif model_name in MODEL_SHORTCUTS:
                    model = MODEL_SHORTCUTS[model_name]
                    print(f"Model switched to {model.name}.")
                else:
                    print(f"Model {model_name!r} not found.")
            else:
                prompt.append({'role': 'user', 'content': user_input})
                chunks = []
                for chunk in query(prompt, model, system_prompt=system_prompt):
                    chunks.append(chunk)
                    print(chunk, end='', flush=True)
                prompt.append({'role': 'assistant', 'content': ''.join(chunks)})

        except KeyboardInterrupt:
            print()
            return


# Entry point

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--model', choices=MODEL_SHORTCUTS.keys(), default='sonnet', help="Model to use for the query")
    parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
    parser.add_argument('-e', '--edit', type=str, help="File to edit")
    parser.add_argument('-s', '--system', type=str, default='', help="System prompt for the model")
    parser.add_argument('-d', '--diff', action='store_true', help="Interpret model response as udiff patches for editing")
    parser.add_argument('-j', '--json', action='store_true', help="Parse the input as json")
    parser.add_argument('-c', '--chat', action='store_true', help="Enable chat mode")
    parser.add_argument('-o', '--output', type=str, help="Output file path for generated code")
    parser.add_argument('question', nargs=argparse.REMAINDER)
    parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
    args = parser.parse_args()

    if not sys.stdin.isatty():
        question = parser.parse_args().stdin.read()
    else:
        question = ' '.join(args.question)

    question = question.strip()
    context: list[str] = []
    if args.file:
        file_paths = list(itertools.chain.from_iterable(glob.glob(fn) for fn in args.file))
        file_paths = list(itertools.chain.from_iterable(list_files(Path(fn)) for fn in file_paths))
        file_data = {path: path.read_text().strip() for path in file_paths}
        context.extend(f'{path}\n```\n{data}\n```' for path, data in file_data.items())
    if args.edit:
        file_path = Path(args.edit)
        context.append(f'{file_path}```\n{file_path.read_text().strip()}\n```')
    if context:
        context_str = '\n\n'.join(context)
        question = f"{context_str}\n\n{question}"

    if args.json:
        assert not args.file and not args.edit, "files not supported in JSON mode"
        prompt = json.loads(question)
    else:
        prompt = [{'role': 'user', 'content': question}]

    model = MODEL_SHORTCUTS[args.model]
    if args.chat:
        assert not args.edit and not args.output, "editing and output not supported in chat mode"
        chat(prompt, model, args.system)
    elif args.edit:
        assert not args.output, "output not supported in edit mode"
        edit(prompt, model, args.system, file_path, args.diff)
    elif args.output:
        output(prompt, model, args.system, Path(args.output))
    else:
        ask(prompt, model, args.system)


if __name__ == '__main__':
    main()
