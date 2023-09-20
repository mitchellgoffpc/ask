#!/usr/bin/env python3
import os
import sys
import json
import argparse
import requests

SHORTCUTS = {'gpt3': 'gpt-3.5-turbo', 'gpt4': 'gpt-4'}

def query(message, model):
  api_key = os.getenv('OPENAI_API_KEY')
  headers = {"Authorization": f"Bearer {api_key}"}
  params = {
    "model": model,
    "messages": [{"role": "user", "content": message}],
    "temperature": 0.7}

  assert api_key, "OPENAI_API_KEY environment variable isn't set!"
  r = requests.post('https://api.openai.com/v1/chat/completions', timeout=None, headers=headers, json=params)

  result = r.json()
  if r.status_code != 200:
    print(json.dumps(result, indent=2))
    raise RuntimeError("Invalid response from API")
  if os.getenv("DEBUG"):
    print(json.dumps(result, indent=2))
  assert len(result['choices']) == 1, f"Expected exactly one choice, but got {len(result['choices'])}!"

  return result['choices'][0]['message']['content']

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-m', '--model', choices=['gpt-3.5-turbo', 'gpt-4', *SHORTCUTS.keys()], default='gpt-4')
  parser.add_argument('-f', '--file')
  parser.add_argument('question', nargs='?')
  parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
  args = parser.parse_args()

  if not sys.stdin.isatty():
    question = parser.parse_args().stdin.read()
  elif args.file:
    with open(args.file) as f:
      question = f.read()
  else:
    question = ' '.join(args.question)

  response = query(question.strip(), SHORTCUTS.get(args.model, args.model))
  print(response)

if __name__ == '__main__':
  main()
