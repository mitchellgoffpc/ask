import base64
import json
import unittest
from unittest.mock import MagicMock

from ask.messages import Message, Text, Image, Reasoning, ToolRequest, ToolResponse, Usage, ToolCallStatus
from ask.models.base import Model
from ask.models.openai import OpenAIAPI
from ask.tools.base import Tool

class TestOpenAIAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = OpenAIAPI('http://api.test', 'TEST_KEY', 'Test')
        self.model = Model('test-model', self.api, [])

    def test_params(self):
        tool = MagicMock(spec=Tool)
        tool.name, tool.description = 'test_tool', 'A test tool'
        tool.get_input_schema.return_value = {'type': 'object', 'properties': {}}

        messages = [
            Message('user', Text('Hello')),
            Message('assistant', Text('Hi')),
            Message('assistant', ToolRequest('call_1', 'test_tool', {'arg': 'value'})),
            Message('user', ToolResponse('call_1', 'test_tool', Text('result'), ToolCallStatus.COMPLETED)),
            Message('user', Image('image/png', b'fakeimagedata')),
        ]

        image_url = 'data:image/png;base64,' + base64.b64encode(b'fakeimagedata').decode()
        expected_input = [
            {'role': 'system', 'content': 'System prompt'},
            {'role': 'user', 'content': [{'type': 'input_text', 'text': 'Hello'}]},
            {'type': 'function_call', 'call_id': 'call_1', 'name': 'test_tool', 'arguments': json.dumps({'arg': 'value'})},
            {'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Hi'}]},
            {'type': 'function_call_output', 'call_id': 'call_1', 'output': [{'type': 'input_text', 'text': 'result'}]},
            {'role': 'user', 'content': [{'type': 'input_image', 'image_url': image_url}]},
        ]

        result = self.api.params(self.model, messages, [tool], 'System prompt', True)
        self.assertEqual(result['model'], 'test-model')
        self.assertTrue(result['stream'])
        self.assertEqual(len(result['tools']), 1)
        for actual, expected in zip(result['input'], expected_input, strict=True):
            self.assertEqual(actual, expected)

    def test_result(self):
        response = {
            'output': [
                {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Hello'}]},
                {'type': 'reasoning', 'encrypted_content': 'encrypted'},
                {'type': 'function_call', 'call_id': 'c1', 'name': 'tool', 'arguments': '{"foo": "bar"}'},
            ],
            'usage': {'input_tokens': 100, 'input_tokens_details': {'cached_tokens': 20}, 'output_tokens': 50}
        }
        expected_output = [
            Text(text='Hello'),
            Reasoning(data='encrypted', summary=None, encrypted=True),
            ToolRequest(call_id='c1', tool='tool', arguments={'foo': 'bar'}),
            Usage(input=100, cache_read=20, cache_write=0, output=50),
        ]

        result = self.api.result(response)
        for actual, expected in zip(result, expected_output, strict=True):
            self.assertEqual(actual, expected)

    async def test_decode(self):
        chunks = [
            {"type": "response.output_text.delta", "output_index": 0, "delta": "Hello"},
            {"type": "response.output_text.delta", "output_index": 0, "delta": " world"},
            {"type": "response.output_item.added", "output_index": 1, "item": {"type": "function_call", "name": "tool", "call_id": "c1", "arguments": ""}},
            {"type": "response.function_call_arguments.delta", "output_index": 1, "delta": "{\"foo\": \"bar\"}"},
            {"type": "response.done", "response": {"usage": {"input_tokens": 10, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 5}}},
        ]

        expected_output = [
            ('Hello', None),
            (' world', None),
            ('', Text('Hello world')),
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
