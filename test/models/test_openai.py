import base64
import json
import unittest

from ask.models.base import Model, Context, Capabilities
from ask.models.openai import OpenAIAPI
from test.models.helpers import INPUT_MESSAGES, RESULT_OUTPUT, DECODE_OUTPUT, to_async

class TestOpenAIAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.api = OpenAIAPI('http://api.test', 'TEST_KEY', 'Test')
        self.model = Model(self.api, 'test-model', [], Context(8192, 4096), None, Capabilities())

    def test_params(self) -> None:
        image_url = 'data:image/png;base64,' + base64.b64encode(b'fakeimagedata').decode()
        expected_output = [
            {'role': 'system', 'content': 'System prompt'},
            {'role': 'user', 'content': [{'type': 'input_text', 'text': 'Hello'}]},
            {'type': 'reasoning', 'encrypted_content': 'i should say hi', 'summary': ['say hello']},
            {'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Hi'}]},
            {'type': 'function_call', 'call_id': 'call_1', 'name': 'test_tool', 'arguments': json.dumps({'arg': 'value'})},
            {'type': 'function_call_output', 'call_id': 'call_1', 'output': [{'type': 'input_text', 'text': 'result'}]},
            {'role': 'user', 'content': [{'type': 'input_image', 'image_url': image_url}]}]

        result = self.api.params(self.model, INPUT_MESSAGES, True)
        self.assertEqual(result['model'], 'test-model')
        self.assertTrue(result['stream'])
        self.assertEqual(len(result['tools']), 1)
        for actual, expected in zip(result['input'], expected_output, strict=True):
            self.assertEqual(actual, expected)

    def test_result(self) -> None:
        response = {
            'output': [
                {'type': 'reasoning', 'encrypted_content': 'encrypted'},
                {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Hello world'}]},
                {'type': 'function_call', 'call_id': 'c1', 'name': 'tool', 'arguments': '{"foo": "bar"}'}],
            'usage': {'input_tokens': 100, 'input_tokens_details': {'cached_tokens': 20}, 'output_tokens': 50}}

        result = self.api.result(response)
        for actual, expected in zip(result, RESULT_OUTPUT, strict=True):
            self.assertEqual(actual, expected)

    async def test_decode(self) -> None:
        chunks = [
            {"type": "response.output_item.done", "output_index": 0, "item": {"type": "reasoning", "encrypted_content": "encrypted", "summary": []}},
            {"type": "response.output_text.delta", "output_index": 1, "delta": "Hello"},
            {"type": "response.output_text.delta", "output_index": 1, "delta": " world"},
            {"type": "response.output_item.added", "output_index": 2, "item": {"type": "function_call", "name": "tool", "call_id": "c1", "arguments": ""}},
            {"type": "response.function_call_arguments.delta", "output_index": 2, "delta": "{\"foo\": \"bar\"}"},
            {"type": "response.done", "response": {"usage": {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 20}, "output_tokens": 50}}}]

        chunk_data = ('data: ' + json.dumps(chunk) async for chunk in to_async(chunks))
        result = [x async for x in self.api.decode(chunk_data)]
        for actual, expected in zip(result, DECODE_OUTPUT, strict=True):
            self.assertEqual(actual, expected)
