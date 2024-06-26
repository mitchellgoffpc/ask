#!/usr/bin/env python3
import sys
import glob
import json
import difflib
import readline
import argparse
import itertools
from pathlib import Path
from ask.query import query
from ask.models import MODELS
from ask.edit import EDIT_SYSTEM_PROMPT, print_diff, apply_edit

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}
LANGUAGE_SHORTCUTS = {'fr': 'french', 'es': 'spanish'}

def read_file(path: Path) -> str:
  with open(path) as f:
    return f.read().strip()

def list_files(path: Path) -> list[Path]:
  if path.name.startswith('.'):
    return []
  elif path.is_file():
    return [path]
  elif path.is_dir():
    return list(itertools.chain.from_iterable(list_files(child) for child in path.iterdir()))


# Ask / Edit / Chat

def ask(prompt, model, system_prompt):
  try:
    chunks = []
    for chunk in query(prompt, MODEL_SHORTCUTS[model], system_prompt=system_prompt):
      print(chunk, end='', flush=True)
      chunks.append(chunk)
    return ''.join(chunks)
  except KeyboardInterrupt:
    return []

def edit(prompt, model, system_prompt, file_path):
  file_data = read_file(file_path)
  response = ask(prompt, model, system_prompt or EDIT_SYSTEM_PROMPT)
  modified = apply_edit(file_data, response)
  print_diff(file_data, modified, file_path)

  user_input = input("Do you want to apply this edit? (y/n): ").strip().lower()
  if user_input == 'y':
    with open(file_path, 'w') as f:
      f.write(modified)
    print(f"Saved edits to {file_path}")

def chat(prompt, model, system_prompt):
  prompt = [msg for msg in prompt if msg['content']]
  while True:
    try:
      user_input = input("> ")
      cmd = user_input.lower().strip().split()
      cmd = cmd[0] if cmd else ''
      if cmd in ('exit', 'quit', '.exit', '.quit', ':exit', ':quit', ':q'):
        return
      elif cmd in ('.models', ':models'):
        print("Available models:")
        for model in MODELS:
          print(f"- {model.name} ({', '.join(model.shortcuts)})")
      elif cmd in ('.model', ':model', ':m'):
        model_name = user_input[len(cmd + ' '):].strip()
        if not model_name:
          print(f"Current model is {MODEL_SHORTCUTS[model].name}.")
        elif model_name in MODEL_SHORTCUTS:
          model = model_name
          print(f"Model switched to {MODEL_SHORTCUTS[model_name].name}.")
        else:
          print(f"Model {model_name!r} not found.")
      else:
        prompt.append({'role': 'user', 'content': user_input})
        chunks = []
        for chunk in query(prompt, MODEL_SHORTCUTS[model], system_prompt=system_prompt):
          chunks.append(chunk)
          print(chunk, end='', flush=True)
        prompt.append({'role': 'assistant', 'content': ''.join(chunks)})

    except KeyboardInterrupt:
      print()
      return


# Entry point

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-m', '--model', choices=MODEL_SHORTCUTS.keys(), default='gpt-3.5-turbo', help="Model to use for the query")
  parser.add_argument('-f', '--file', action='append', default=[], help="Files to use as context for the request")
  parser.add_argument('-e', '--edit', type=str, help="File to edit")
  parser.add_argument('-t', '--translate', type=str, help="Language to translate into")
  parser.add_argument('-s', '--system', type=str, help="System prompt for the model")
  parser.add_argument('-j', '--json', action='store_true', help="Parse the input as json")
  parser.add_argument('-c', '--chat', action='store_true', help="Enable chat mode")
  parser.add_argument('question', nargs=argparse.REMAINDER)
  parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
  args = parser.parse_args()

  if not sys.stdin.isatty():
    question = parser.parse_args().stdin.read()
  else:
    question = ' '.join(args.question)

  question = question.strip()
  if args.translate:
    language = LANGUAGE_SHORTCUTS.get(args.translate, args.translate)
    question = f'How do I translate "{question}" into {language}?'

  context = []
  if args.file:
    file_paths = list(itertools.chain.from_iterable(glob.glob(fn) for fn in args.file))
    file_paths = list(itertools.chain.from_iterable(list_files(Path(fn)) for fn in file_paths))
    file_data = {path: read_file(path) for path in file_paths}
    context.extend(f'{path}\n```\n{data}\n```' for path, data in file_data.items())
  if args.edit:
    file_path = str(Path(args.edit))
    file_data = read_file(file_path)
    context.append(f'{file_path}```\n{file_data}\n```')
  if context:
    question = f"{'\n\n'.join(context)}\n\n{question}"

  if args.json:
    assert not args.file and not args.edit, "files not supported in JSON mode"
    prompt = json.loads(question)
  else:
    prompt = [{'role': 'user', 'content': question}]

  if args.chat:
    assert not args.edit, "editing not supported in chat mode"
    chat(prompt, args.model, args.system)
  elif args.edit:
    edit(prompt, args.model, args.system, file_path)
  else:
    ask(prompt, args.model, args.system)


if __name__ == '__main__':
  main()
