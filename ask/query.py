import asyncio
import aiohttp
import json
import os
from dataclasses import replace
from typing import AsyncIterator, Awaitable, Callable

from ask.messages import Message, Content, Text, Command, Usage, ToolRequest, CheckedToolRequest, ToolResponse, ToolCallStatus, Reasoning
from ask.models import Model
from ask.models.tool_helpers import parse_tool_block
from ask.prompts import load_prompt_file
from ask.tools import TOOLS, Tool, ToolError

AsyncContentIterator = AsyncIterator[tuple[str, Content | None]]
AsyncMessageIterator = AsyncIterator[tuple[str, Message | None]]
ApprovalCallback = Callable[[CheckedToolRequest], Awaitable[bool]]

def _expand_commands(old_messages: list[Message]) -> list[Message]:
    new_messages = []
    for message in old_messages:
        match message.content:
            case Command(): new_messages.extend(message.content.messages())
            case _: new_messages.append(message)
    return new_messages

async def _execute_tool(request: CheckedToolRequest, approval: ApprovalCallback) -> ToolResponse:
    tool_rejected_message = load_prompt_file('tools.toml')['tool_rejected_prompt']
    try:
        tool = TOOLS[request.tool]
        if not await approval(request):
            return ToolResponse(call_id=request.call_id, tool=request.tool, response=Text(tool_rejected_message), status=ToolCallStatus.CANCELLED)
        output = await tool.run(**request.processed_arguments)
        return ToolResponse(call_id=request.call_id, tool=request.tool, response=output, status=ToolCallStatus.COMPLETED)
    except asyncio.CancelledError:
        return ToolResponse(call_id=request.call_id, tool=request.tool, response=Text(tool_rejected_message), status=ToolCallStatus.CANCELLED)
    except Exception as e:
        return ToolResponse(call_id=request.call_id, tool=request.tool, response=Text(str(e)), status=ToolCallStatus.FAILED)


# Make a single query to the model API

async def _query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str, stream: bool) -> AsyncContentIterator:
    messages = _expand_commands(messages)
    api = model.api
    api_key = os.getenv(api.key, '')
    stream = stream and model.stream
    url = api.url(model, stream)
    params = api.params(model, messages, tools, system_prompt, stream)
    headers = api.headers(api_key)
    assert api_key, f"{api.key!r} environment variable isn't set!"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=params) as r:
            if r.status != 200:
                try:
                    response_json = await r.json()
                    response_text = json.dumps(response_json, indent=2)
                except aiohttp.ContentTypeError:
                    response_text = await r.text()
                raise RuntimeError(f"Invalid response from API ({r.status})\n{response_text}")

            if stream:
                async for delta, content in api.decode(line.decode('utf-8') async for line in r.content):
                    yield delta, content
            else:
                try:
                    response_json = await r.json()
                    for item in api.result(response_json):
                        yield '', item
                except aiohttp.ContentTypeError:
                    response_text = await r.text()
                    raise RuntimeError(f"Invalid response from API ({r.status})\n{response_text}") from None

async def query(model: Model, messages: list[Message], tools: list[Tool], system_prompt: str, stream: bool = True) -> AsyncContentIterator:
    async for chunk, content in _query(model, messages, tools, system_prompt, stream):
        if isinstance(content, Usage):
            yield chunk, replace(content, model=model.name)
        elif isinstance(content, Text) and not model.supports_tools:
            yield chunk, None
            for item in parse_tool_block(content):
                yield '', item
        else:
            yield chunk, content


# Run agent loop until completion

async def query_agent(model: Model, messages: list[Message], tools: list[Tool],
                      approval: ApprovalCallback, system_prompt: str, stream: bool = True) -> AsyncMessageIterator:
    messages = messages[:]
    while True:
        has_text, has_reasoning, has_tool_requests = False, False, False
        tool_requests: list[CheckedToolRequest] = []
        async for delta, content in query(model, messages, tools, system_prompt, stream):
            match content:
                case None:
                    yield delta, None
                case ToolRequest(call_id=call_id, tool=tool_name, arguments=args) as request:
                    has_tool_requests = True
                    try:
                        tool = TOOLS[tool_name]
                        checked_request = CheckedToolRequest(call_id=call_id, tool=tool_name, arguments=args, processed_arguments=tool.check(args))
                        tool_requests.append(checked_request)
                        messages.append(Message('assistant', checked_request))
                        yield delta, Message('assistant', checked_request)
                    except ToolError as e:
                        messages.append(Message('assistant', request))
                        messages.append(Message('user', ToolResponse(call_id=call_id, tool=tool_name, response=Text(str(e)), status=ToolCallStatus.FAILED)))
                        yield delta, None
                case _:
                    match content:
                        case Reasoning(): has_reasoning = True
                        case Text(): has_text = True
                    messages.append(Message('assistant', content))
                    yield delta, Message('assistant', content)

        if not (has_tool_requests or (has_reasoning and not has_text)):
            return
        if tool_requests:
            tasks = [asyncio.create_task(_execute_tool(req, approval)) for req in tool_requests]
            tool_responses = [Message(role='user', content=r) for r in await asyncio.gather(*tasks)]
            for response in tool_responses:
                yield '', response
            messages.extend(tool_responses)
