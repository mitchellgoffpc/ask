#!/usr/bin/env python3
import os
import json
import argparse
import requests

def query(message, model):
  api_key = os.getenv('OPENAI_API_KEY')
  headers = {"Authorization": f"Bearer {api_key}"}
  params = {
    "model": model,
    "messages": [{"role": "user", "content": message}],
    "temperature": 0.7}

  assert api_key, "OPENAI_API_KEY environment variable isn't set!"
  r = requests.post('https://api.openai.com/v1/chat/completions', timeout=60, headers=headers, json=params)

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
  parser.add_argument('-m', '--model', choices=['gpt-3.5-turbo', 'gpt-4'], default='gpt-3.5-turbo')
  parser.add_argument('question', nargs='+')
  args = parser.parse_args()
  response = query(' '.join(args.question), args.model)
  print(response)

if __name__ == '__main__':
  main()
