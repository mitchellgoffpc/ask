import base64
import json
import unittest

from ask.models.base import Model, Context, Capabilities
from ask.models.anthropic import AnthropicAPI
from test.models.helpers import INPUT_MESSAGES, RESULT_OUTPUT, DECODE_OUTPUT, to_async

class TestAnthropicAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = AnthropicAPI('http://api.test', 'TEST_KEY', 'Test')
        self.model = Model(self.api, 'test-model', [], Context(8192, 4096), None, Capabilities())

    def test_params(self):
        image_data = base64.b64encode(b'fakeimagedata').decode()
        expected_output = [
            {'role': 'user', 'content': [{'type': 'text', 'text': 'Hello'}]},
            {'role': 'assistant', 'content': [
                {'type': 'thinking', 'signature': 'i should say hi', 'thinking': 'say hello'},
                {'type': 'text', 'text': 'Hi'},
                {'type': 'tool_use', 'id': 'call_1', 'name': 'test_tool', 'input': {'arg': 'value'}}]},
            {'role': 'user', 'content': [
                {'type': 'tool_result', 'tool_use_id': 'call_1', 'content': [{'type': 'text', 'text': 'result'}]},
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': image_data}, 'cache_control': {'type': 'ephemeral'}}]}]

        result = self.api.params(self.model, INPUT_MESSAGES, True)
        self.assertEqual(result['model'], 'test-model')
        self.assertTrue(result['stream'])
        self.assertEqual(len(result['tools']), 1)
        self.assertEqual(result['system'], [{'type': 'text', 'text': 'System prompt', 'cache_control': {'type': 'ephemeral'}}])
        for actual, expected in zip(result['messages'], expected_output, strict=True):
            self.assertEqual(actual, expected)

    def test_result(self):
        response = {
            'content': [
                {'type': 'thinking', 'signature': 'encrypted', 'thinking': ''},
                {'type': 'text', 'text': 'Hello world'},
                {'type': 'tool_use', 'id': 'c1', 'name': 'tool', 'input': {'foo': 'bar'}}],
            'usage': {'input_tokens': 100, 'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 20, 'output_tokens': 50}}

        result = self.api.result(response)
        for actual, expected in zip(result, RESULT_OUTPUT, strict=True):
            self.assertEqual(actual, expected)

    async def test_decode(self):
        chunks = [
            {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "encrypted"}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Hello"}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": " world"}},
            {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "c1", "name": "tool", "input": ""}},
            {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": "{\"foo\": \"bar\"}"}},
            {"type": "message_delta", "usage": {"input_tokens": 100, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 20, "output_tokens": 50}}]

        chunk_data = ('data: ' + json.dumps(chunk) async for chunk in to_async(chunks))
        result = [x async for x in self.api.decode(chunk_data)]
        for actual, expected in zip(result, DECODE_OUTPUT, strict=True):
            self.assertEqual(actual, expected)
