import json
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from uuid import UUID, uuid4
from typing import Any, get_args

from ask.tools import ToolCallStatus
from ask.models import MODELS_BY_NAME, Model, Message, Role, Content
from ask.ui.core.components import dirty

class MessageEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return {'__type__': 'Path', 'path': str(obj)}
        elif isinstance(obj, UUID):
            return {'__type__': 'UUID', 'uuid': str(obj)}
        elif isinstance(obj, Model):
            return {'__type__': 'Model', 'name': obj.name}
        elif isinstance(obj, Content):
            data = obj.__dict__.copy()
            data['__type__'] = obj.__class__.__name__
            return data
        elif isinstance(obj, ToolCallStatus):
            return {'__type__': 'ToolCallStatus', 'value': obj.value}
        return super().default(obj)

def message_decoder(obj):
    if isinstance(obj, dict) and obj.get('__type__') == 'Path':
        return Path(obj['path'])
    elif isinstance(obj, dict) and obj.get('__type__') == 'UUID':
        return UUID(obj['uuid'])
    elif isinstance(obj, dict) and obj.get('__type__') == 'Model':
        return MODELS_BY_NAME[obj['name']]
    elif isinstance(obj, dict) and obj.get('__type__') in [cls.__name__ for cls in get_args(Content)]:
        type_name = obj.pop('__type__')
        content_types = {cls.__name__: cls for cls in get_args(Content)}
        return content_types[type_name](**obj)
    elif isinstance(obj, dict) and obj.get('__type__') == 'ToolCallStatus':
        return ToolCallStatus(obj['value'])
    return obj

class MessageTree:
    def __init__(self, parent_uuid: UUID, messages: dict[UUID, Message]) -> None:
        self.parent_uuid = parent_uuid
        self.messages = messages.copy()
        self.parents = {child: parent for parent, child in pairwise((None, *messages.keys()))}

    def __getitem__(self, key: UUID) -> Message:
        return self.messages[key]

    def __setitem__(self, key: UUID, value: Message) -> None:
        self.messages[key] = value
        dirty.add(self.parent_uuid)

    def clear(self) -> None:
        self.messages.clear()
        self.parents.clear()
        dirty.add(self.parent_uuid)

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
