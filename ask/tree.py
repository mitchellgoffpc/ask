import base64
import json
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from uuid import UUID, uuid4
from typing import Any, Callable, get_args

from ask.messages import ToolCallStatus, Message, Role, Content

class MessageEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, bytes):
            return {'__type__': 'bytes', 'data': base64.b64encode(obj).decode()}
        elif isinstance(obj, Path):
            return {'__type__': 'Path', 'path': str(obj)}
        elif isinstance(obj, UUID):
            return {'__type__': 'UUID', 'uuid': str(obj)}
        elif isinstance(obj, Content):
            data = obj.__dict__.copy()
            data['__type__'] = obj.__class__.__name__
            return data
        elif isinstance(obj, ToolCallStatus):
            return {'__type__': 'ToolCallStatus', 'value': obj.value}
        return super().default(obj)

def message_decoder(obj: Any) -> Any:
    content_types = {cls.__name__: cls for cls in get_args(Content)}
    if isinstance(obj, dict) and obj.get('__type__') == 'bytes':
        return base64.b64decode(obj['data'])
    if isinstance(obj, dict) and obj.get('__type__') == 'Path':
        return Path(obj['path'])
    elif isinstance(obj, dict) and obj.get('__type__') == 'UUID':
        return UUID(obj['uuid'])
    elif isinstance(obj, dict) and obj.get('__type__') in content_types:
        type_name = obj.pop('__type__')
        return content_types[type_name](**obj)
    elif isinstance(obj, dict) and obj.get('__type__') == 'ToolCallStatus':
        return ToolCallStatus(obj['value'])
    return obj

class MessageTree:
    def __init__(self, messages: dict[UUID, Message], onchange: Callable[[], None] | None = None) -> None:
        self.messages = messages.copy()
        self.parents = {child: parent for parent, child in pairwise((None, *messages.keys()))}
        self.onchange = onchange or (lambda: None)

    def __getitem__(self, key: UUID) -> Message:
        return self.messages[key]

    def __setitem__(self, key: UUID, value: Message) -> None:
        self.messages[key] = value
        self.onchange()

    def clear(self) -> None:
        self.messages.clear()
        self.parents.clear()
        self.onchange()

    def keys(self, head: UUID | None) -> list[UUID]:
        keys = []
        while head is not None:
            keys.append(head)
            head = self.parents[head]
        return keys[::-1]

    def values(self, head: UUID | None) -> list[Message]:
        return [self.messages[k] for k in self.keys(head)]

    def items(self, head: UUID | None) -> list[tuple[UUID, Message]]:
        return list(zip(self.keys(head), self.values(head), strict=True))

    def add(self, role: Role, head: UUID | None, content: Content, uuid: UUID | None = None) -> UUID:
        message_uuid = uuid or uuid4()
        self[message_uuid] = Message(role=role, content=content)
        self.parents[message_uuid] = head
        return message_uuid

    def update(self, uuid: UUID, content: Content) -> None:
        self[uuid] = replace(self[uuid], content=content)

    def dump(self) -> list[dict[str, Any]]:
        return [{'uuid': uuid, 'parent': self.parents[uuid], 'role': msg.role, 'content': msg.content} for uuid, msg in self.messages.items()]

    def load(self, data: list[dict[str, Any]]) -> None:
        self.clear()
        for message in data:
            self[message['uuid']] = Message(role=message['role'], content=message['content'])
            self.parents[message['uuid']] = message['parent']
