import base64
import json
import unittest

from ask.models.base import Capabilities, Context, Model
from ask.models.legacy import LegacyOpenAIAPI
from tests.models.helpers import DECODE_OUTPUT, INPUT_MESSAGES, RESULT_OUTPUT, to_async


class TestLegacyOpenAIAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.api = LegacyOpenAIAPI('http://api.test', 'TEST_KEY', 'Test')
        self.model = Model(self.api, 'test-model', [], Context(8192, 4096), None, Capabilities())

    def test_params(self) -> None:
        image_url = 'data:image/png;base64,' + base64.b64encode(b'fakeimagedata').decode()
        expected_output = [
            {'role': 'system', 'content': 'System prompt'},
            {'role': 'user', 'content': [{'type': 'text', 'text': 'Hello'}]},
            {'role': 'assistant',
             'content': [{'type': 'reasoning', 'reasoning': 'i should say hi'}, {'type': 'text', 'text': 'Hi'}],
             'tool_calls': [{'id': 'call_1', 'type': 'function', 'function': {'name': 'test_tool', 'arguments': '{"arg": "value"}'}}]},
            {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'result'},
            {'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': image_url}}]}]

        result = self.api.params(self.model, INPUT_MESSAGES, True)
        assert result['model'] == 'test-model'
        assert result['stream']
        assert len(result['tools']) == 1
        for actual, expected in zip(result['messages'], expected_output, strict=True):
            assert actual == expected

    def test_result(self) -> None:
        response = {
            'choices': [{
                'message': {
                    'content': 'Hello world',
                    'reasoning': 'encrypted',
                    'tool_calls': [{'id': 'c1', 'function': {'name': 'tool', 'arguments': '{"foo": "bar"}'}}]}}]}

        result = self.api.result(response)
        for actual, expected in zip(result, RESULT_OUTPUT[:-1], strict=True):
            assert actual == expected

    async def test_decode(self) -> None:
        chunks = [
            {"choices": [{"index": 0, "delta": {"content": "Hello"}}]},
            {"choices": [{"index": 0, "delta": {"content": " world"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "tool", "arguments": "{\"foo\": \"bar\"}"}}]}}]}]

        chunk_data = ('data: ' + json.dumps(chunk) async for chunk in to_async(chunks))
        result = [x async for x in self.api.decode(chunk_data)]
        for actual, expected in zip(result, DECODE_OUTPUT[1:-1], strict=True):
            assert actual == expected
