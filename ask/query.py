import os
import json
import requests
from typing import Iterator
from ask.tools import Tool
from ask.models import Message, Model, Content

def query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> Iterator[tuple[str, Content | None]]:
    api = model.api
    api_key = os.getenv(api.key, '')
    params = api.params(model, messages, tools, system_prompt)
    headers = api.headers(api_key)
    assert api_key, f"{api.key!r} environment variable isn't set!"
    with requests.post(api.url, timeout=None, headers=headers, json=params, stream=model.stream) as r:
        if r.status_code != 200:
            try:
                print(json.dumps(r.json(), indent=2))
            except requests.exceptions.JSONDecodeError:
                print(r.text)
            raise RuntimeError("Invalid response from API")
        if model.stream:
            yield from api.decode(line.decode('utf-8') for line in r.iter_lines())
        else:
            try:
                for item in api.result(r.json()):
                    yield '', item
            except requests.exceptions.JSONDecodeError as e:
                print(r.text)
                raise RuntimeError("Invalid response from API") from e
