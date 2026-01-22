import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from ask.messages import Message, Text, Reasoning, ToolDescriptor, ToolRequest, CheckedToolRequest, ToolResponse, Usage, ToolCallStatus
from ask.models.base import Model
from ask.models.openai import OpenAIAPI
from ask.query import query_agent
from ask.tools.base import Tool
from test.models.helpers import to_async

def create_mock_tool(name='test_tool', description='A test tool'):
    tool = MagicMock(spec=Tool)
    tool.name = name
    tool.description = description
    tool.get_input_schema.return_value = {'type': 'object', 'properties': {}}
    return tool

class TestQueryAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = OpenAIAPI('http://api.test', 'TEST_KEY', 'Test')
        self.model = Model('test-model', self.api, [])
        self.tool = create_mock_tool('test_tool', 'A test tool')
        self.tool.check.return_value = {'arg': 'processed_value'}
        self.approval = AsyncMock(return_value=True)

    async def test_agent_loop_simple_response(self):
        initial_messages = [Message('user', Text('Hello'))]
        query_responses = [[('', Text('Hi there'))]]
        expected = [Message('assistant', Text('Hi there'))]

        with patch('ask.query.query', side_effect=[to_async(r) for r in query_responses]):
            results = [msg async for _, msg in query_agent(self.model, initial_messages, self.approval, False) if msg is not None]
        for result, exp in zip(results, expected, strict=True):
            self.assertEqual(result, exp)

    async def test_agent_loop_reasoning_only(self):
        initial_messages = [Message('user', Text('Hello'))]
        query_responses = [
            [('', Reasoning(data='thinking', encrypted=True))],
            [('', Text('Response'))]]
        expected = [
            Message('assistant', Reasoning(data='thinking', encrypted=True)),
            Message('assistant', Text('Response'))]

        with patch('ask.query.query', side_effect=[to_async(r) for r in query_responses]):
            results = [msg async for _, msg in query_agent(self.model, initial_messages, self.approval, False) if msg is not None]
        for result, exp in zip(results, expected, strict=True):
            self.assertEqual(result, exp)

    async def test_agent_loop_with_tool_call(self):
        initial_messages = [
            Message('user', ToolDescriptor(self.tool.name, self.tool.description, self.tool.get_input_schema())),
            Message('user', Text('Hello'))]
        query_responses = [
            [('', Reasoning(data='thinking', encrypted=True)),
             ('', ToolRequest('call_1', 'test_tool', {'arg': 'value'}))],
            [('Hello', None),
             (' there', None),
             ('', Text('Hello there')),
             ('', Usage(input=100, cache_read=0, cache_write=0, output=50))]]
        expected = [
            Message('assistant', Reasoning(data='thinking', encrypted=True)),
            Message('assistant', CheckedToolRequest('call_1', 'test_tool', {'arg': 'value'}, {'arg': 'processed_value'})),
            Message('user', ToolResponse('call_1', 'test_tool', Text('tool result'), ToolCallStatus.COMPLETED)),
            Message('assistant', Text('Hello there')),
            Message('assistant', Usage(input=100, cache_read=0, cache_write=0, output=50))]

        with patch('ask.query.TOOLS', {'test_tool': self.tool}), \
             patch('ask.query.query', side_effect=[to_async(r) for r in query_responses]), \
             patch('ask.query._execute_tool', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = ToolResponse('call_1', 'test_tool', Text('tool result'), ToolCallStatus.COMPLETED)
            results = [msg async for _, msg in query_agent(self.model, initial_messages, self.approval, False) if msg is not None]
            mock_execute.assert_called_once()
        for result, exp in zip(results, expected, strict=True):
            self.assertEqual(result, exp)
