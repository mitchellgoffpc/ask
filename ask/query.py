import json
import os
import aiohttp
from typing import AsyncIterator
from uuid import UUID, uuid4

from ask.tools import TOOLS, Tool
from ask.edit import apply_edits
from ask.models import Model, Message, Content, Text, Reasoning, ToolRequest, ToolResponse, Status
from ask.models.tool_helpers import parse_tool_block

# High-level ask/act functions

async def ask(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> dict[UUID, Content]:
    contents = {}
    async for chunk, content in query(model, messages, tools, system_prompt):
        print(chunk, end='', flush=True)
        if content:
            contents[uuid4()] = content
    if model.stream:
        print()  # trailing newline
    else:
        for content in contents.values():
            if isinstance(content, Text):
                print(content.text)
            elif isinstance(content, Reasoning):
                print(f'<think>\n{content.text}\n</think>')
    return contents

async def act(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> list[Message]:
    try:
        while True:
            response = await ask(model, messages, tools, system_prompt)
            response_text = '\n\n'.join(item.text for item in response if isinstance(item, Text))
            apply_edits(response_text)

            tool_results: dict[UUID, Content] = {}
            for item in response.values():
                if isinstance(item, ToolRequest):
                    if item.tool in TOOLS:
                        result = TOOLS[item.tool](item.arguments)
                    else:
                        result = f"Tool {item.tool} not found"
                    tool_results[uuid4()] = ToolResponse(call_id=item.call_id, tool=item.tool, response=result, status=Status.COMPLETED)

            if tool_results:
                messages.append(Message(role="assistant", content=response))
                messages.append(Message(role="user", content=tool_results))
            else:
                break

    except KeyboardInterrupt:
        print('\n')

    return messages


# Query the model

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
