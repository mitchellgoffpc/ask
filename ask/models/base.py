import json
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, replace
from typing import Any, AsyncIterator, Optional, Union

from ask.tools import Tool, ToolCallStatus

TOOL_IMAGE_ERROR_MSG = "Function call returned an image, but the API does not support this behavior. The image will be attached manually by the user instead."

Content = Union['Text', 'Reasoning', 'Image', 'ToolRequest', 'ToolResponse', 'Command', 'Usage', 'Error']

def get_message_groups(messages: list['Message']) -> list[tuple[str, list[Content]]]:
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


# Message classes

@dataclass
class Message:
    role: str
    content: Content

@dataclass
class Text:
    text: str

@dataclass
class Reasoning:
    data: str
    summary: str | None = None
    encrypted: bool = False

@dataclass
class Image:
    mimetype: str
    data: bytes

@dataclass
class ToolRequest:
    call_id: str
    tool: str
    arguments: dict[str, str]
    processed_arguments: dict[str, Any] | None = None

@dataclass
class ToolResponse:
    call_id: str
    tool: str
    response: Text | Image
    status: ToolCallStatus

@dataclass
class Command(metaclass=ABCMeta):
    command: str

    def render_command(self) -> str:
        return self.command

    @abstractmethod
    def messages(self) -> list[Message]: ...

@dataclass
class Usage:
    input: int
    cache_write: int
    cache_read: int
    output: int
    model: Optional['Model'] = None

@dataclass
class Error:
    text: str


# Model / API classes

@dataclass
class Pricing:
    input: float
    cache_write: float
    cache_read: float
    output: float

@dataclass
class Model:
    name: str
    api: 'API'
    shortcuts: list[str]
    pricing: Pricing | None = None
    stream: bool = True
    supports_tools: bool = True
    supports_images: bool = True
    supports_system_prompt: bool = True
    supports_reasoning: bool = True


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
    def render_reasoning(self, reasoning: Reasoning) -> dict[str, Any]: ...

    @abstractmethod
    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]: ...

    @abstractmethod
    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]: ...

    def render_content(self, role: str, content: Content, model: Model) -> list[dict[str, Any]]:
        if isinstance(content, Usage):
            return []
        elif isinstance(content, Text):
            return [self.render_response_text(content) if role == 'assistant' else self.render_text(content)]
        elif isinstance(content, Image):
            if not model.supports_images:
                raise NotImplementedError(f"Model '{model.name}' does not support image prompts")
            return [self.render_image(content)]
        elif isinstance(content, ToolRequest):
            return [self.render_tool_request(content)]
        elif isinstance(content, ToolResponse):
            if isinstance(content.response, Image) and not self.supports_image_tools:
                return [
                    self.render_tool_response(replace(content, response=Text(TOOL_IMAGE_ERROR_MSG))),
                    self.render_image(content.response)]
            else:
                return [self.render_tool_response(content)]
        elif isinstance(content, Reasoning):
            return [self.render_reasoning(content)]
        else:
            raise TypeError(f"Unsupported message content: {type(content)}")

    @abstractmethod
    def render_tool(self, tool: Tool) -> dict[str, Any]: ...

    # Request / Response

    def url(self, model: Model, stream: bool) -> str:
        return self.base_url

    @abstractmethod
    def headers(self, api_key: str) -> dict[str, str]: ...

    @abstractmethod
    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str, stream: bool) -> dict[str, Any]: ...

    @abstractmethod
    def result(self, response: dict[str, Any]) -> list[Content]: ...

    async def decode(self, chunks: AsyncIterator[str]) -> AsyncIterator[tuple[str, Content | None]]:
        current_idx, current_tool = '', ''
        current_data: list[str] = []
        current_usage: Usage | None = None
        async for chunk in chunks:
            idx, tool, data, usage = self.decode_chunk(chunk)
            if idx and idx != current_idx:
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
            summary = None
            if '\x00' in data:
                summary, data = data.split('\x00', 1)
            return '', Reasoning(data=data, summary=summary, encrypted='encrypted' in tags)
        elif tool:
            assert ':' in tool, "Expected tool to be formatted as <name>:<call-id>"
            tool_name, call_id = tool.rsplit(':', 1)
            return '', ToolRequest(call_id=call_id, tool=tool_name, arguments=json.loads(data))
        elif data:
            return '', Text(text=data)
        else:
            return '', None
