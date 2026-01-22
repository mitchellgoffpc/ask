import base64
import json
import unittest
from unittest.mock import patch

from ask.models.base import Model
from ask.models.google import GoogleAPI
from test.models.helpers import INPUT_MESSAGES, RESULT_OUTPUT, DECODE_OUTPUT, to_async

class TestGoogleAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = GoogleAPI('http://api.test', 'TEST_KEY', 'Test')
        self.model = Model('test-model', self.api, [])

    def test_params(self):
        image_data = base64.b64encode(b'fakeimagedata').decode()
        expected_output = [
            {'role': 'user', 'parts': [{'text': 'Hello'}]},
            {'role': 'model', 'parts': [{'text': 'Hi'}, {'functionCall': {'name': 'test_tool', 'args': {'arg': 'value'}}}]},
            {'role': 'user', 'parts': [
                {'functionResponse': {'name': 'test_tool', 'response': {'result': 'result'}}},
                {'inline_data': {'mime_type': 'image/png', 'data': image_data}}]}]

        result = self.api.params(self.model, INPUT_MESSAGES[:3] + INPUT_MESSAGES[4:], True)
        self.assertEqual(result['system_instruction'], {'parts': [{'text': 'System prompt'}]})
        self.assertEqual(len(result['tools'][0]['functionDeclarations']), 1)
        for actual, expected in zip(result['contents'], expected_output, strict=True):
            self.assertEqual(actual, expected)

    def test_result(self):
        response = {
            'candidates': [{
                'content': {
                    'parts': [
                        {'text': 'Hello world'},
                        {'functionCall': {'name': 'tool', 'args': {'foo': 'bar'}}}]}}]}

        with patch('ask.models.google.uuid4', return_value='c1'):
            result = self.api.result(response)
        for actual, expected in zip(result, RESULT_OUTPUT[1:-1], strict=True):
            self.assertEqual(actual, expected)

    async def test_decode(self):
        chunks = [
            {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]},
            {"candidates": [{"content": {"parts": [{"text": " world"}]}}]},
            {"candidates": [{"content": {"parts": [{"functionCall": {"name": "tool", "args": {"foo": "bar"}}}]}}]}]

        chunk_data = ('data: ' + json.dumps(chunk) async for chunk in to_async(chunks))
        with patch('ask.models.google.uuid4', return_value='c1'):
            result = [x async for x in self.api.decode(chunk_data)]
        for actual, expected in zip(result, DECODE_OUTPUT[1:-1], strict=True):
            self.assertEqual(actual, expected)
