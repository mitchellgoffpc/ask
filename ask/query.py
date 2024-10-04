import os
import json
import requests
from typing import Iterator
from ask.models import Prompt, Model, TextModel

def query_text(prompt: Prompt, model: Model, system_prompt: str = '', prompt_caching=False) -> Iterator[str]:
    if not isinstance(model, TextModel):
        raise RuntimeError(f"This operation requires a model that can generate text, but the model you selected is {model}.")
    for chunk in query_bytes(prompt, model, system_prompt=system_prompt, prompt_caching=prompt_caching):
        yield chunk.decode('utf-8')

def query_bytes(prompt: Prompt, model: Model, system_prompt: str = '', prompt_caching=False) -> Iterator[bytes]:
    api = model.api
    api_key = os.getenv(api.key, '')
    params = api.params(model.name, prompt, system_prompt)
    headers = api.headers(api_key, prompt_caching=prompt_caching)
    assert api_key, f"{api.key!r} environment variable isn't set!"
    with requests.post(api.url, timeout=None, headers=headers, json=params, stream=api.stream) as r:
        if r.status_code != 200:
            result = r.json()
            print(json.dumps(result, indent=2))
            raise RuntimeError("Invalid response from API")
        if api.stream:
            for line in r.iter_lines():
                yield api.decode(line.decode('utf-8'))
        else:
            yield api.result(r.json())
