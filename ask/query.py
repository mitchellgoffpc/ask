import os
import json
import requests
from typing import List, Dict, Union

Message = Union[str, List[Dict[str, str]]]


def query(message: Message, model: str) -> str:
  assert isinstance(message, (list, str))
  if isinstance(message, str):
    message = [{"role": "user", "content": message}]

  api_key = os.getenv('OPENAI_API_KEY')
  headers = {"Authorization": f"Bearer {api_key}"}
  params = {"model": model, "messages": message, "temperature": 0.7}

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
