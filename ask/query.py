import json
import os
import aiohttp
from typing import AsyncIterator

from ask.tools import Tool
from ask.models import Model, Message, Content, Text
from ask.models.tool_helpers import parse_tool_block

async def query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> AsyncIterator[tuple[str, Content | None]]:
    async for chunk, content in _query(model, messages, tools, system_prompt):
        if isinstance(content, Text) and not model.supports_tools:
            yield chunk, None
            for item in parse_tool_block(content):
                yield '', item
        else:
            yield chunk, content

async def _query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> AsyncIterator[tuple[str, Content | None]]:
    api = model.api
    api_key = os.getenv(api.key, '')
    params = api.params(model, messages, tools, system_prompt)
    headers = api.headers(api_key)
    assert api_key, f"{api.key!r} environment variable isn't set!"

    async with aiohttp.ClientSession() as session:
        async with session.post(api.url, headers=headers, json=params) as r:
            if r.status != 200:
                try:
                    response_json = await r.json()
                    print(json.dumps(response_json, indent=2))
                except aiohttp.ContentTypeError:
                    response_text = await r.text()
                    print(response_text)
                raise RuntimeError("Invalid response from API")

            if model.stream:
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
