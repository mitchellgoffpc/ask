from __future__ import annotations
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

class ToolCallStatus(Enum):
    PENDING = 'pending'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'

@dataclass
class SystemPrompt:
    text: str

@dataclass
class Text:
    text: str

@dataclass
class Image:
    mimetype: str
    data: bytes

@dataclass
class PDF:
    name: str
    data: bytes

@dataclass
class Reasoning:
    data: str
    summary: str = ''
    encrypted: bool = False

@dataclass
class ToolDescriptor:
    name: str
    description: str
    input_schema: dict[str, Any]

@dataclass
class ToolRequest:
    call_id: str
    tool: str
    arguments: dict[str, str]

@dataclass
class CheckedToolRequest(ToolRequest):
    processed_arguments: dict[str, Any]

@dataclass
class ToolResponse:
    call_id: str
    tool: str
    response: Blob
    status: ToolCallStatus

@dataclass
class Command(metaclass=ABCMeta):
    command: str

    @abstractmethod
    def messages(self) -> list[Message]: ...

    def render_command(self) -> str:
        return self.command

@dataclass
class Usage:
    input: int
    cache_write: int
    cache_read: int
    output: int

@dataclass
class Error:
    text: str

@dataclass
class Message:
    role: Role
    content: Content

Role = Literal['user', 'assistant']
Blob = Text | Image | PDF
Content = Blob | Reasoning | ToolDescriptor | ToolRequest | ToolResponse | Command | Usage | Error | SystemPrompt
