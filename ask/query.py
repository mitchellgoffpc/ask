import os
import json
import requests
from typing import Iterator
from ask.tools import TOOLS, Tool
from ask.edit import apply_edits
from ask.models import Model, Message, Content, Text, Reasoning, ToolRequest, ToolResponse
from ask.models.tool_helpers import parse_tool_block

# High-level ask/act functions

def ask(model: Model, messages: list[Message], tools: list, system_prompt: str) -> list[Content]:
    contents = []
    for chunk, content in query(model, messages, tools, system_prompt):
        print(chunk, end='', flush=True)
        if content:
            contents.append(content)
    if model.stream:
        print()  # trailing newline
    else:
        for content in contents:
            if isinstance(content, Text):
                print(content.text)
            elif isinstance(content, Reasoning):
                print(f'<think>\n{content.text}\n</think>')
    return contents

def act(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> list[Message]:
    try:
        while True:
            response = ask(model, messages, tools, system_prompt)
            response_text = '\n\n'.join(item.text for item in response if isinstance(item, Text))
            apply_edits(response_text)

            tool_results: list[Content] = []
            for item in response:
                if isinstance(item, ToolRequest):
                    if item.tool in TOOLS:
                        result = TOOLS[item.tool](item.arguments)
                    else:
                        result = f"Tool {item.tool} not found"
                    tool_results.append(ToolResponse(call_id=item.call_id, tool=item.tool, response=result))

            if tool_results:
                messages.append(Message(role="assistant", content=response))
                messages.append(Message(role="user", content=tool_results))
            else:
                break

    except KeyboardInterrupt:
        print('\n')

    return messages


# Query the model

def query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> Iterator[tuple[str, Content | None]]:
    for chunk, content in _query(model, messages, tools, system_prompt):
        if isinstance(content, Text) and not model.supports_tools:
            yield chunk, None
            for item in parse_tool_block(content):
                yield '', item
        else:
            yield chunk, content

def _query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str) -> Iterator[tuple[str, Content | None]]:
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
