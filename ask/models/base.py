import json
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Union
from uuid import UUID

from ask.tools import Tool

Content = Union['Text', 'Reasoning', 'Image', 'ToolRequest', 'ToolResponse', 'ShellCommand']

class Status(Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

@dataclass
class Text:
    text: str
    hidden: bool = False

@dataclass
class Reasoning:
    text: str

@dataclass
class Image:
    mimetype: str
    data: bytes

@dataclass
class ToolRequest:
    call_id: str
    tool: str
    arguments: dict[str, str]

@dataclass
class ToolResponse:
    call_id: str
    tool: str
    response: str
    status: Status

@dataclass
class ShellCommand:
    command: str
    output: str
    error: str
    status: Status

@dataclass
class Message:
    role: str
    content: dict[UUID, Content]

@dataclass
class Model:
    name: str
    api: 'API'
    shortcuts: list[str]
    stream: bool = True
    supports_tools: bool = True
    supports_images: bool = True
    supports_system_prompt: bool = True


@dataclass
class API(metaclass=ABCMeta):
    key: str
    url: str

    # Rendering

    def render_text(self, text: Text) -> dict[str, Any]:
        return {'type': 'text', 'text': text.text}

    @abstractmethod
    def render_image(self, image: Image) -> dict[str, Any]: ...

    @abstractmethod
    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]: ...

    @abstractmethod
    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]: ...

    def render_content(self, content: Content, model: Model) -> list[dict[str, Any]]:
        if isinstance(content, Text):
            return [self.render_text(content)]
        elif isinstance(content, Reasoning):
            return []  # Don't render reasoning for now
        elif isinstance(content, Image):
            if not model.supports_images:
                raise NotImplementedError(f"Model '{model.name}' does not support image prompts")
            return [self.render_image(content)]
        elif isinstance(content, ToolRequest):
            return [self.render_tool_request(content)]
        elif isinstance(content, ToolResponse):
            return [self.render_tool_response(content)]
        elif isinstance(content, ShellCommand):
            if content.status is Status.CANCELLED:
                output = "[Request interrupted by user]"
            else:
                output = f"<bash-stdout>{content.output}</bash-stdout><bash-stderr>{content.error}</bash-stderr>"
            return [self.render_text(Text(f"<bash-stdin>{content.command}</bash-stdin>")), self.render_text(Text(output))]
        else:
            raise TypeError(f"Unsupported message content: {type(content)}")

    @abstractmethod
    def render_tool(self, tool: Tool) -> dict[str, Any]: ...

    # Request / Response

    @abstractmethod
    def headers(self, api_key: str) -> dict[str, str]: ...

    @abstractmethod
    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]: ...

    @abstractmethod
    def result(self, response: dict[str, Any]) -> list[Content]: ...

    async def decode(self, chunks: AsyncIterator[str]) -> AsyncIterator[tuple[str, Content | None]]:
        current_idx, current_tool = '', ''
        current_data: list[str] = []
        async for chunk in chunks:
            idx, tool, data = self.decode_chunk(chunk)
            if idx and idx != current_idx:
                yield self.flush_content(current_idx, idx, current_tool, ''.join(current_data))
                current_idx, current_tool, current_data = idx, '', []
            current_tool = current_tool or tool
            current_data.append(data)
            if not current_tool:
                yield data, None
        yield self.flush_content(current_idx, '', current_tool, ''.join(current_data))

    @abstractmethod
    def decode_chunk(self, chunk: str) -> tuple[str, str, str]: ...

    def flush_content(self, current_idx: str, next_idx: str, tool: str, data: str) -> tuple[str, Content | None]:
        if tool:
            assert ':' in tool, "Expected tool to be formatted as <name>:<call-id>"
            tool_name, call_id = tool.rsplit(':', 1)
            return '', ToolRequest(call_id=call_id, tool=tool_name, arguments=json.loads(data))
        elif data:
            return '', Text(text=data)
        else:
            return '', None
