from __future__ import annotations
import json
from abc import ABCMeta, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from typing import Any

from ask.messages import Message, Role, Content, Text, Image, PDF, Reasoning, ToolDescriptor, ToolRequest, ToolResponse, Usage, SystemPrompt

TOOL_IMAGE_ERROR_MSG = "Function call returned an image, but the API does not support this behavior. The image will be attached manually by the user instead."

def get_message_groups(messages: list[Message]) -> list[tuple[Role, list[Content]]]:
    if not messages:
        return []
    groups = []
    current_role = messages[0].role
    current_group = [messages[0].content]
    for message in messages[1:]:
        if isinstance(message.content, Usage):
            continue
        elif message.role == current_role:
            current_group.append(message.content)
        else:
            groups.append((current_role, current_group))
            current_role = message.role
            current_group = [message.content]
    return groups + [(current_role, current_group)]


# Model / API classes

@dataclass
class Context:
    max_length: int
    max_output_length: int

@dataclass
class Pricing:
    input: float
    cache_write: float
    cache_read: float
    output: float

@dataclass
class Capabilities:
    stream: bool = True
    images: bool = True
    pdfs: bool = True
    system_prompt: bool = True
    reasoning: bool = True

@dataclass
class Model:
    api: API
    name: str
    shortcuts: list[str]
    context: Context
    pricing: Pricing | None
    capabilities: Capabilities


class API(metaclass=ABCMeta):
    supports_image_tools: bool = False

    def __init__(self, url: str, key: str, display_name: str):
        self.key = key
        self.base_url = url
        self.display_name = display_name

    # Rendering

    @abstractmethod
    def render_text(self, text: Text) -> dict[str, Any]: ...

    def render_response_text(self, text: Text) -> dict[str, Any]:
        return self.render_text(text)

    @abstractmethod
    def render_image(self, image: Image) -> dict[str, Any]: ...

    @abstractmethod
    def render_pdf(self, pdf: PDF) -> dict[str, Any]: ...

    @abstractmethod
    def render_reasoning(self, reasoning: Reasoning) -> dict[str, Any]: ...

    @abstractmethod
    def render_tool_descriptor(self, tool: ToolDescriptor) -> dict[str, Any]: ...

    @abstractmethod
    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]: ...

    @abstractmethod
    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]: ...

    @abstractmethod
    def render_system_prompt(self, system_prompt: SystemPrompt, model: Model) -> list[dict[str, Any]]: ...

    def render_content(self, role: str, content: Content, model: Model) -> list[dict[str, Any]]:
        match content:
            case Usage() | SystemPrompt(): return []
            case Text(): return [self.render_response_text(content) if role == 'assistant' else self.render_text(content)]
            case Image() if not model.capabilities.images:
                raise NotImplementedError(f"Model '{model.name}' does not support image prompts")
            case Image(): return [self.render_image(content)]
            case PDF() if not model.capabilities.pdfs:
                raise NotImplementedError(f"Model '{model.name}' does not support PDF prompts")
            case PDF(): return [self.render_pdf(content)]
            case Reasoning(): return [self.render_reasoning(content)]
            case ToolRequest(): return [self.render_tool_request(content)]
            case ToolResponse(response=Image() as response) if not self.supports_image_tools:
                return [
                    self.render_tool_response(replace(content, response=Text(TOOL_IMAGE_ERROR_MSG))),
                    self.render_image(response)]
            case ToolResponse(): return [self.render_tool_response(content)]
            case _: raise TypeError(f"Unsupported message content: {type(content)}")

    @abstractmethod
    def render_messages(self, messages: list[Message], model: Model) -> dict[str, Any]: ...

    # Request / Response

    def url(self, model: Model, stream: bool) -> str:
        return self.base_url

    @abstractmethod
    def headers(self, api_key: str) -> dict[str, str]: ...

    @abstractmethod
    def params(self, model: Model, messages: list[Message], stream: bool) -> dict[str, Any]: ...

    @abstractmethod
    def result(self, response: dict[str, Any]) -> list[Content]: ...

    async def decode(self, chunks: AsyncIterator[str]) -> AsyncIterator[tuple[str, Content | None]]:
        current_idx, current_tool = '', ''
        current_data: list[str] = []
        current_usage: Usage | None = None
        async for chunk in chunks:
            idx, tool, data, usage = self.decode_chunk(chunk)
            if idx and idx != current_idx:
                if current_idx:
                    yield self.flush_content(current_idx, idx, current_tool, ''.join(current_data))
                current_idx, current_tool, current_data = idx, '', []
            current_usage = usage or current_usage
            current_tool = tool or current_tool
            current_data.append(data)
            if not current_tool:
                yield data, None
        yield self.flush_content(current_idx, '', current_tool, ''.join(current_data))
        if current_usage:
            yield '', current_usage

    @abstractmethod
    def decode_chunk(self, chunk: str) -> tuple[str, str, str, Usage | None]: ...

    def flush_content(self, current_idx: str, next_idx: str, tool: str, data: str) -> tuple[str, Content | None]:
        if tool.startswith('/reasoning'):
            _, *tags = tool.split(':')
            summary = ''
            return '', Reasoning(data=data, summary=summary, encrypted='encrypted' in tags)
        elif tool:
            assert ':' in tool, "Expected tool to be formatted as <name>:<call-id>"
            tool_name, call_id = tool.rsplit(':', 1)
            return '', ToolRequest(call_id=call_id, tool=tool_name, arguments=json.loads(data))
        elif data:
            return '', Text(text=data)
        else:
            return '', None
