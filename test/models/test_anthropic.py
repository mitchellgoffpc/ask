import base64
import json
import unittest
from unittest.mock import MagicMock

from ask.messages import Message, Text, Image, Reasoning, ToolRequest, ToolResponse, Usage, ToolCallStatus
from ask.models.base import Model
from ask.models.anthropic import AnthropicAPI
from ask.tools.base import Tool

class TestAnthropicAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = AnthropicAPI('http://api.test', 'TEST_KEY', 'Test')
        self.model = Model('test-model', self.api, [])

    def test_params(self):
        tool = MagicMock(spec=Tool)
        tool.name, tool.description = 'test_tool', 'A test tool'
        tool.get_input_schema.return_value = {'type': 'object', 'properties': {}}

        messages = [
            Message('user', Text('Hello')),
            Message('assistant', Reasoning(data='i should say hi', summary='say hello', encrypted=True)),
            Message('assistant', Text('Hi')),
            Message('assistant', ToolRequest('call_1', 'test_tool', {'arg': 'value'})),
            Message('user', ToolResponse('call_1', 'test_tool', Text('result'), ToolCallStatus.COMPLETED)),
            Message('user', Image('image/png', b'fakeimagedata'))]

        image_data = base64.b64encode(b'fakeimagedata').decode()
        expected_messages = [
            {'role': 'user', 'content': [{'type': 'text', 'text': 'Hello'}]},
            {'role': 'assistant', 'content': [
                {'type': 'thinking', 'signature': 'i should say hi', 'thinking': 'say hello'},
                {'type': 'text', 'text': 'Hi'},
                {'type': 'tool_use', 'id': 'call_1', 'name': 'test_tool', 'input': {'arg': 'value'}}]},
            {'role': 'user', 'content': [
                {'type': 'tool_result', 'tool_use_id': 'call_1', 'content': [{'type': 'text', 'text': 'result'}]},
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': image_data}, 'cache_control': {'type': 'ephemeral'}}]}]

        result = self.api.params(self.model, messages, [tool], 'System prompt', True)
        self.assertEqual(result['model'], 'test-model')
        self.assertTrue(result['stream'])
        self.assertEqual(len(result['tools']), 1)
        self.assertEqual(result['system'], [{'type': 'text', 'text': 'System prompt', 'cache_control': {'type': 'ephemeral'}}])
        for actual, expected in zip(result['messages'], expected_messages, strict=True):
            self.assertEqual(actual, expected)

    def test_result(self):
        response = {
            'content': [
                {'type': 'text', 'text': 'Hello'},
                {'type': 'thinking', 'signature': 'sig123', 'thinking': 'thought'},
                {'type': 'tool_use', 'id': 'c1', 'name': 'tool', 'input': {'foo': 'bar'}},
            ],
            'usage': {'input_tokens': 100, 'cache_creation_input_tokens': 10, 'cache_read_input_tokens': 20, 'output_tokens': 50}
        }
        expected_output = [
            Text(text='Hello'),
            Reasoning(data='sig123', summary='thought', encrypted=True),
            ToolRequest(call_id='c1', tool='tool', arguments={'foo': 'bar'}),
            Usage(input=100, cache_read=20, cache_write=10, output=50),
        ]

        result = self.api.result(response)
        for actual, expected in zip(result, expected_output, strict=True):
            self.assertEqual(actual, expected)

    async def test_decode(self):
        chunks = [
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " world"}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "thinking_delta", "thinking": "thinking"}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "signature_delta", "signature": "sig123"}},
            {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "c1", "name": "tool", "input": ""}},
            {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "{\"foo\": \"bar\"}"}},
            {"type": "message_delta", "usage": {"input_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 5}},
        ]

        expected_output = [
            ('Hello', None),
            (' world', None),
            ('', Text('Hello world')),
            ('', Reasoning(data='sig123', summary='thinking', encrypted=True)),
            ('', ToolRequest(call_id='c1', tool='tool', arguments={'foo': 'bar'})),
            ('', Usage(input=10, cache_read=0, cache_write=0, output=5)),
        ]

        async def chunk_iterator():
            for chunk in chunks:
                yield 'data: ' + json.dumps(chunk)

        result = []
        async for delta, content in self.api.decode(chunk_iterator()):
            result.append((delta, content))
        for actual, expected in zip(result, expected_output, strict=True):
            self.assertEqual(actual, expected)
