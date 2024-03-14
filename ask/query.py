import os
import json
import requests
from typing import List, Dict, Union
from ask.models import Model

Message = Union[str, List[Dict[str, str]]]


def query(message: Message, model: Model) -> str:
  assert isinstance(message, (list, str))
  if isinstance(message, str):
    message = [{"role": "user", "content": message}]

  api = model.api
  api_key = os.getenv(api.key)
  assert api_key, f"{api.key!r} environment variable isn't set!"
  r = requests.post(api.url, timeout=None, headers=api.headers(api_key), json=api.params(model.name, message))

  result = r.json()
  if r.status_code != 200:
    print(json.dumps(result, indent=2))
    raise RuntimeError("Invalid response from API")
  if os.getenv("DEBUG"):
    print(json.dumps(result, indent=2))
  return api.result(result)
