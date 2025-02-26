import os
import json
import requests
from typing import Iterator
from ask.models import Message, Model, TextModel
from ask.tools import Tool

def query_text(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> Iterator[str]:
    if not isinstance(model, TextModel):
        raise RuntimeError(f"This operation requires a model that can generate text, but the model you selected is {model}.")
    for chunk in query_bytes(model, messages, tools, system_prompt=system_prompt):
        yield chunk.decode('utf-8')

def query_bytes(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> Iterator[bytes]:
    api = model.api
    api_key = os.getenv(api.key, '')
    params = api.params(model.name, messages, tools, system_prompt)
    headers = api.headers(api_key)
    assert api_key, f"{api.key!r} environment variable isn't set!"
    with requests.post(api.url, timeout=None, headers=headers, json=params, stream=api.stream) as r:
        if r.status_code != 200:
            result = r.json()
            print(json.dumps(result, indent=2))
            raise RuntimeError("Invalid response from API")
        if api.stream:
            yield from api.decode(line.decode('utf-8') for line in r.iter_lines())
        else:
            yield api.result(r.json())
