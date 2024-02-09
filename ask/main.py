#!/usr/bin/env python3
import sys
import glob
import json
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

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-m', '--model', choices=MODEL_SHORTCUTS.keys(), default='gpt-3.5-turbo')
  parser.add_argument('-f', '--file', action='append', default=[])
  parser.add_argument('-t', '--translate')
  parser.add_argument('-j', '--json', action='store_true')
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
    question = json.loads(question)

  response = query(question, MODEL_SHORTCUTS[args.model])
  print(response)


if __name__ == '__main__':
  main()
