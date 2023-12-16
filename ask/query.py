import os
import json
import requests
from typing import List, Dict, Union
from ask.models import Model, APIS

Message = Union[str, List[Dict[str, str]]]


def query(message: Message, model: Model) -> str:
  assert isinstance(message, (list, str))
  if isinstance(message, str):
    message = [{"role": "user", "content": message}]

  api = APIS[model.api]
  api_key = os.getenv(api.key)
  headers = {"Authorization": f"Bearer {api_key}"}
  params = {"model": model.name, "messages": message, "temperature": 0.7}

  assert api_key, f"{api.key!r} environment variable isn't set!"
  r = requests.post(api.url, timeout=None, headers=headers, json=params)

  result = r.json()
  if r.status_code != 200:
    print(json.dumps(result, indent=2))
    raise RuntimeError("Invalid response from API")
  if os.getenv("DEBUG"):
    print(json.dumps(result, indent=2))
  assert len(result['choices']) == 1, f"Expected exactly one choice, but got {len(result['choices'])}!"

  return result['choices'][0]['message']['content']
