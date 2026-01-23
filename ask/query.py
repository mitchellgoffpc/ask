import asyncio
import aiohttp
import json
import os
import re
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable
from uuid import UUID, uuid4

from ask.commands import SlashCommand, BashCommand, FilesCommand, InitCommand, ModelCommand, PythonCommand
from ask.commands import load_messages, save_messages, get_usage, get_current_model
from ask.messages import Message, Content, Text, Command, ToolRequest, ToolResponse, ToolCallStatus, Reasoning
from ask.models import MODEL_SHORTCUTS, MODELS_BY_NAME
from ask.prompts import load_prompt_file
from ask.tools import TOOLS, ToolError
from ask.tools.read import read_file
from ask.tree import MessageTree

AsyncContentIterator = AsyncIterator[tuple[str, Content | None]]
AsyncMessageIterator = AsyncIterator[tuple[str, Message | None]]
ApprovalCallback = Callable[[ToolRequest], Awaitable[bool]]

def _expand_commands(old_messages: list[Message]) -> list[Message]:
    new_messages = []
    for message in old_messages:
        match message.content:
            case Command(): new_messages.extend(message.content.messages())
            case _: new_messages.append(message)
    return new_messages

async def _execute_tool(request: ToolRequest, approval: ApprovalCallback) -> ToolResponse:
    tool_rejected_message = load_prompt_file('tools.toml')['tool_rejected_prompt']
    try:
        tool = TOOLS[request.tool]
        if not await approval(request):
            return ToolResponse(call_id=request.call_id, tool=request.tool, response=Text(tool_rejected_message), status=ToolCallStatus.CANCELLED)
        output = await tool.run(request.arguments, request.artifacts)
        return ToolResponse(call_id=request.call_id, tool=request.tool, response=output, status=ToolCallStatus.COMPLETED)
    except asyncio.CancelledError:
        return ToolResponse(call_id=request.call_id, tool=request.tool, response=Text(tool_rejected_message), status=ToolCallStatus.CANCELLED)
    except Exception as e:
        return ToolResponse(call_id=request.call_id, tool=request.tool, response=Text(str(e)), status=ToolCallStatus.FAILED)


# Make a single query to the model API

async def query(messages: list[Message], stream: bool) -> AsyncContentIterator:
    model = get_current_model(messages)
    messages = _expand_commands(messages)
    api = model.api
    api_key = os.getenv(api.key, '')
    stream = stream and model.capabilities.stream
    url = api.url(model, stream)
    params = api.params(model, messages, stream)
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


# Run agent loop until completion

async def query_agent(messages: list[Message], approval: ApprovalCallback, stream: bool = True) -> AsyncMessageIterator:
    messages = messages[:]
    while True:
        has_text, has_reasoning, has_tool_requests = False, False, False
        tool_requests: list[ToolRequest] = []
        async for delta, content in query(messages, stream):
            match content:
                case None:
                    yield delta, None
                case ToolRequest(call_id=call_id, tool=tool_name, arguments=args):
                    has_tool_requests = True
                    try:
                        tool = TOOLS[tool_name]
                        tool.check(args)
                        request = ToolRequest(call_id=call_id, tool=tool_name, arguments=args, _artifacts=tool.artifacts(args))
                        tool_requests.append(request)
                        messages.append(Message('assistant', request))
                        yield delta, Message('assistant', request)
                    except ToolError as e:
                        request = ToolRequest(call_id=call_id, tool=tool_name, arguments=args)
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

        async def reject(_: ToolRequest) -> bool: return False
        for req in tool_requests:
            response = await _execute_tool(req, approval)
            if response.status == ToolCallStatus.CANCELLED:
                approval = reject
            messages.append(Message('user', response))
            yield '', Message('user', response)
        if approval is reject:
            return


# Main entry point for the UI to query the agent with commands

async def query_agent_with_commands(messages: MessageTree, head: UUID, query: str,
                                    approval: ApprovalCallback, stream: bool = True) -> AsyncIterator[UUID]:
    current_model = get_current_model(messages.values(head))
    if query == '/clear':
        messages.clear()
        yield messages.add('user', None, ModelCommand(command='', model=current_model.name))
    elif query == '/init':
        yield messages.add('user', head, InitCommand(command='/init'))
    elif query == '/cost':
        yield messages.add('user', head, SlashCommand(command='/cost', output=get_usage(messages, head)))
    elif query.startswith('/save '):
        yield save_messages(query.removeprefix('/save').strip(), messages, head)
    elif query.startswith('/load '):
        yield load_messages(query.removeprefix('/load').strip(), messages, head)
    elif query.startswith('/bash '):
        head, tasks = BashCommand.create(query.removeprefix('/bash ').strip(), messages, head)
        yield head
        await asyncio.gather(*tasks)
    elif query.startswith('/python '):
        head, tasks = PythonCommand.create(query.removeprefix('/python ').strip(), messages, head)
        yield head
        await asyncio.gather(*tasks)
    elif query.startswith('/model'):
        model_name = query.removeprefix('/model').lstrip()
        if not model_name:
            model_list = '\n'.join(f"  {name} ({m.api.display_name})" for name, m in MODELS_BY_NAME.items())
            yield messages.add('user', head, SlashCommand(command='/model', output=f"Available models:\n{model_list}"))
        elif model_name not in MODEL_SHORTCUTS:
            yield messages.add('user', head, SlashCommand(command=f'/model {model_name}', error=f"Unknown model: {model_name}"))
        elif (full_model_name := MODEL_SHORTCUTS[model_name].name) != current_model.name:
            output = f"Switched from {current_model.name} to {full_model_name}"
            yield messages.add('user', head, ModelCommand(command=f'/model {model_name}', output=output, model=full_model_name))
    else:
        file_paths = [Path(m[1:]) for m in re.findall(r'@\S+', query) if Path(m[1:]).is_file()]  # get file attachments
        if file_paths:
            head = messages.add('user', head, FilesCommand(file_contents={fp: read_file(fp) for fp in file_paths}))
        head = messages.add('user', head, Text(query))
        yield head

        text_uuid: UUID | None = None
        text = ''
        async for delta, msg in query_agent(messages.values(head), approval, stream):
            text = text + delta
            if text and text_uuid not in messages.messages:
                text_uuid = uuid4()
                yield (head := messages.add('assistant', head, Text(''), uuid=text_uuid))
            elif text and text_uuid is not None:
                messages.update(text_uuid, Text(text))

            if msg and msg.role == 'user':
                yield (head := messages.add('user', head, msg.content))
            if msg and msg.role == 'assistant':
                match msg.content:
                    case Text() if text_uuid:
                        messages.update(text_uuid, msg.content)
                        text = ''
                        text_uuid = None
                    case _:
                        yield (head := messages.add('assistant', head, msg.content))
