#!/usr/bin/env python3
import sys
import argparse
from ask.query import query
from ask.models import MODELS

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}
LANGUAGE_SHORTCUTS = {'fr': 'french', 'es': 'spanish'}


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-m', '--model', choices=MODEL_SHORTCUTS.keys(), default='gpt-3.5-turbo')
  parser.add_argument('-f', '--file')
  parser.add_argument('-c', '--context')
  parser.add_argument('-t', '--translate')
  parser.add_argument('question', nargs=argparse.REMAINDER)
  parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
  args = parser.parse_args()

  if not sys.stdin.isatty():
    question = parser.parse_args().stdin.read()
  elif args.file:
    with open(args.file) as f:
      question = f.read()
  else:
    question = ' '.join(args.question)

  question = question.strip()
  if args.translate:
    language = LANGUAGE_SHORTCUTS.get(args.translate, args.translate)
    question = f'How do I translate "{question}" into {language}?'
  if args.context:
    with open(args.context) as f:
      context = f.read().strip()
      question = f"{question}\n\n```\n{context}\n```"

  response = query(question, MODEL_SHORTCUTS[args.model])
  print(response)


if __name__ == '__main__':
  main()
