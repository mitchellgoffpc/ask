import aiohttp
import json
import os
from dataclasses import replace
from typing import AsyncIterator

from ask.tools import Tool
from ask.models import Model, Message, Content, Text, Usage
from ask.models.tool_helpers import parse_tool_block

AsyncContentIterator = AsyncIterator[tuple[str, Content | None]]

async def query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str, stream: bool = True) -> AsyncContentIterator:
    async for chunk, content in _query(model, messages, tools, system_prompt, stream):
        if isinstance(content, Usage):
            yield chunk, replace(content, model=model)
        elif isinstance(content, Text) and not model.supports_tools:
            yield chunk, None
            for item in parse_tool_block(content):
                yield '', item
        else:
            yield chunk, content

async def _query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str, stream: bool) -> AsyncContentIterator:
    api = model.api
    api_key = os.getenv(api.key, '')
    stream = stream and model.stream
    url = api.url(model, stream)
    params = api.params(model, messages, tools, system_prompt, stream)
    headers = api.headers(api_key)
    assert api_key, f"{api.key!r} environment variable isn't set!"

    if int(os.getenv("ASK_DEBUG", "0")):
        with open('/tmp/ask.json', 'w') as f:
            json.dump(params, f, indent=2)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=params) as r:
            if r.status != 200:
                try:
                    response_json = await r.json()
                    print(json.dumps(response_json, indent=2))
                except aiohttp.ContentTypeError:
                    response_text = await r.text()
                    print(response_text)
                raise RuntimeError("Invalid response from API")

            if stream:
                async for delta, content in api.decode(line.decode('utf-8') async for line in r.content):
                    yield delta, content
            else:
                try:
                    response_json = await r.json()
                    for item in api.result(response_json):
                        yield '', item
                except aiohttp.ContentTypeError as e:
                    response_text = await r.text()
                    print(response_text)
                    raise RuntimeError("Invalid response from API") from e
