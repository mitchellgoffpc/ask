import json
from abc import ABCMeta, abstractmethod
from typing import Any, Iterator
from dataclasses import dataclass
from ask.tools import Tool, Parameter

@dataclass
class Text:
    text: str

@dataclass
class Image:
    mimetype: str
    data: bytes

@dataclass
class ToolRequest:
    tool: str
    arguments: dict[str, str]

@dataclass
class ToolResponse:
    tool: str
    response: str

@dataclass
class Message:
    role: str
    content: list[Text | Image]

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

    def render_text(self, text: str) -> dict[str, Any]:
        return {'type': 'text', 'text': text}

    def render_item(self, item: Text | Image, model: Model) -> dict[str, Any]:
        if isinstance(item, Text):
            return self.render_text(item.text)
        else:
            if not model.supports_images:
                raise NotImplementedError(f"Model '{model.name}' does not support image prompts")
            return self.render_image(item.mimetype, item.data)

    def render_message(self, message: Message, model: Model) -> dict[str, Any]:
        return {'role': message.role, 'content': [self.render_item(item, model) for item in message.content]}

    def render_tool_param(self, param: Parameter) -> dict[str, Any]:
        rendered: dict[str, Any] = {'type': param.type}
        if param.description:
            rendered['description'] = param.description
        if param.enum:
            rendered['enum'] = param.enum
        return rendered

    def decode(self, chunks: Iterator[str]) -> Iterator[tuple[str, Text | Image | ToolRequest | None]]:
        current_idx, current_tool = '', ''
        current_data: list[str] = []
        for chunk in chunks:
            idx, tool, data = self.decode_chunk(chunk)
            if idx and idx != current_idx:
                yield self.flush_content(current_idx, idx, current_tool, ''.join(current_data))
                current_idx, current_tool, current_data = idx, '', []
            current_tool = current_tool or tool
            current_data.append(data)
            if not current_tool:
                yield data, None
        yield self.flush_content(current_idx, '', current_tool, ''.join(current_data))

    def flush_content(self, current_idx: str, next_idx: str, tool: str, data: str) -> tuple[str, Text | Image | ToolRequest | None]:
        if tool:
            return '', ToolRequest(tool=tool, arguments=json.loads(data))
        elif data:
            return '', Text(text=data)
        else:
            return '', None

    @abstractmethod
    def render_image(self, mimetype: str, data: bytes) -> dict[str, Any]: ...

    @abstractmethod
    def render_tool(self, tool: Tool) -> dict[str, Any]: ...

    @abstractmethod
    def headers(self, api_key: str) -> dict[str, str]: ...

    @abstractmethod
    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]: ...

    @abstractmethod
    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]: ...

    @abstractmethod
    def decode_chunk(self, chunk: str) -> tuple[str, str, str]: ...
