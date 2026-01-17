from unittest.mock import MagicMock

from ask.messages import Message, Text, Image, Reasoning, ToolRequest, ToolResponse, Usage, ToolCallStatus
from ask.tools.base import Tool

INPUT_MESSAGES = [
    Message('user', Text('Hello')),
    Message('assistant', Reasoning(data='i should say hi', encrypted=True, summary='say hello')),
    Message('assistant', Text('Hi')),
    Message('assistant', ToolRequest('call_1', 'test_tool', {'arg': 'value'})),
    Message('user', ToolResponse('call_1', 'test_tool', Text('result'), ToolCallStatus.COMPLETED)),
    Message('user', Image('image/png', b'fakeimagedata')),
]

RESULT_OUTPUT = [
    Text(text='Hello world'),
    Reasoning(data='encrypted', encrypted=True),
    ToolRequest(call_id='c1', tool='tool', arguments={'foo': 'bar'}),
    Usage(input=100, cache_read=20, cache_write=0, output=50),
]

DECODE_OUTPUT = [
    ('Hello', None),
    (' world', None),
] + [('', x) for x in RESULT_OUTPUT]


def create_mock_tool(name='test_tool', description='A test tool'):
    tool = MagicMock(spec=Tool)
    tool.name = name
    tool.description = description
    tool.get_input_schema.return_value = {'type': 'object', 'properties': {}}
    return tool

async def to_async(data):
    for item in data:
        yield item
