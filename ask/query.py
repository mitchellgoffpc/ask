import os
import json
import requests
from typing import Generator
from ask.models import Model, Prompt


def query(prompt: Prompt, model: Model, system_prompt: str = '') -> Generator[str, None, None]:
  assert isinstance(prompt, (list, str))
  if isinstance(prompt, str):
    prompt = [{"role": "user", "content": prompt}]

  api = model.api
  api_key = os.getenv(api.key)
  params = api.params(model.name, prompt, system_prompt)
  assert api_key, f"{api.key!r} environment variable isn't set!"
  with requests.post(api.url, timeout=None, headers=api.headers(api_key), json=params, stream=True) as r:
    if r.status_code != 200:
      result = r.json()
      print(json.dumps(result, indent=2))
      raise RuntimeError("Invalid response from API")
    for line in r.iter_lines():
      yield api.decode(line.decode('utf-8'))
    yield "\n"
