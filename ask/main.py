#!/usr/bin/env python3
import sys
import glob
import json
import readline
import argparse
import itertools
from typing import List
from pathlib import Path
from ask.query import query
from ask.models import MODELS

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}
LANGUAGE_SHORTCUTS = {'fr': 'french', 'es': 'spanish'}

def read_file(path: Path) -> str:
  with open(path) as f:
    return f.read().strip()

def list_files(path: Path) -> List[Path]:
  if path.name.startswith('.'):
    return []
  elif path.is_file():
    return [path]
  elif path.is_dir():
    return list(itertools.chain.from_iterable(list_files(child) for child in path.iterdir()))


# Ask / Chat

def ask(prompt, model, system_prompt):
  try:
    for chunk in query(prompt, MODEL_SHORTCUTS[model], system_prompt=system_prompt):
      print(chunk, end='', flush=True)
  except KeyboardInterrupt:
    pass

def chat(prompt, model, system_prompt):
  while True:
    try:
      user_input = input("> ")
      cmd = user_input.lower().strip().split()
      cmd = cmd[0] if cmd else ''
      if cmd in ('exit', 'quit', '.exit', '.quit', ':exit', ':quit', ':q'):
        return
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
  parser.add_argument('-m', '--model', choices=MODEL_SHORTCUTS.keys(), default='gpt-3.5-turbo')
  parser.add_argument('-f', '--file', action='append', default=[])
  parser.add_argument('-t', '--translate')
  parser.add_argument('-s', '--system')
  parser.add_argument('-j', '--json', action='store_true')
  parser.add_argument('-c', '--chat', action='store_true')
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
  if args.file:
    file_paths = list(itertools.chain.from_iterable(glob.glob(fn) for fn in args.file))
    file_paths = list(itertools.chain.from_iterable(list_files(Path(fn)) for fn in file_paths))
    file_data = {path: read_file(path) for path in file_paths}
    context = '\n\n'.join(f'{path}\n```\n{data}\n```' for path, data in file_data.items())
    question = f"{context}\n\n{question}"

  if args.json:
    assert not args.file, "files not supported in JSON mode"
    prompt = json.loads(question)
  else:
    prompt = [{'role': 'user', 'content': question}]

  if args.chat:
    chat(prompt, args.model, args.system)
  else:
    ask(prompt, args.model, args.system)


if __name__ == '__main__':
  main()
