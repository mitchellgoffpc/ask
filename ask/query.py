
import os
import json
import requests
from typing import List, Dict, Union, Generator
from ask.models import Model

Message = Union[str, List[Dict[str, str]]]


def query(message: Message, model: Model) -> Generator[str, None, None]:
  assert isinstance(message, (list, str))
  if isinstance(message, str):
    message = [{"role": "user", "content": message}]

  api = model.api
  api_key = os.getenv(api.key)
  assert api_key, f"{api.key!r} environment variable isn't set!"
  with requests.post(api.url, timeout=None, headers=api.headers(api_key), json=api.params(model.name, message), stream=True) as r:
    if r.status_code != 200:
      result = r.json()
      print(json.dumps(result, indent=2))
      raise RuntimeError("Invalid response from API")
    for line in r.iter_lines():
      yield api.decode(line.decode('utf-8'))
    yield "\n"
