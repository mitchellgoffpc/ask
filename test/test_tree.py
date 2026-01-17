import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from uuid import uuid4

from ask.messages import Message, Text, Image, PDF, ToolRequest, CheckedToolRequest, ToolResponse, ToolCallStatus
from ask.tools import TOOL_LIST
from ask.tree import MessageTree, MessageEncoder, message_decoder

class TestMessageTree(unittest.TestCase):
    def setUp(self):
        self.tree = MessageTree(uuid4(), {})

    def test_add(self):
        msg_uuid = self.tree.add('user', None, Text('hello'))
        self.assertEqual(self.tree[msg_uuid].role, 'user')
        self.assertEqual(self.tree[msg_uuid].content, Text('hello'))

    def test_update(self):
        msg_uuid = self.tree.add('user', None, Text('original'))
        self.tree.update(msg_uuid, Text('updated'))
        self.assertEqual(self.tree[msg_uuid].content, Text('updated'))

    def test_clear(self):
        self.tree.add('user', None, Text('first'))
        self.tree.add('assistant', None, Text('second'))
        self.tree.clear()
        self.assertEqual(len(self.tree.messages), 0)
        self.assertEqual(len(self.tree.parents), 0)

    def test_keys_values(self):
        msg1 = self.tree.add('user', None, Text('first'))
        msg2 = self.tree.add('assistant', msg1, Text('second'))
        msg3 = self.tree.add('user', msg2, Text('third'))

        keys = self.tree.keys(msg3)
        self.assertEqual(keys, [msg1, msg2, msg3])
        values = self.tree.values(msg2)
        self.assertEqual(values, [Message(role='user', content=Text('first')), Message(role='assistant', content=Text('second'))])
        items = self.tree.items(msg2)
        self.assertEqual(items, [(msg1, Message(role='user', content=Text('first'))), (msg2, Message(role='assistant', content=Text('second')))])


class TestEncoderDecoder(unittest.TestCase):
    def test_image_encode_decode(self):
        message = Image(mimetype='image/png', data=b'\x89PNG\r\n\x1a\n')
        encoded = json.dumps(message, cls=MessageEncoder)
        decoded = json.loads(encoded, object_hook=message_decoder)
        self.assertEqual(decoded.data, message.data)

    def test_pdf_encode_decode(self):
        message = PDF(name='test.pdf', data=b'%PDF-1.4')
        encoded = json.dumps(message, cls=MessageEncoder)
        decoded = json.loads(encoded, object_hook=message_decoder)
        self.assertEqual(decoded.data, message.data)

    def test_tool_request_encode_decode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file_path = str(Path(temp_dir) / 'test.txt')
            dummy_args: dict[str, dict[str, Any]] = {
                'BashShell': {'command': 'echo test'},
                'Edit': {'file_path': test_file_path, 'old_string': 'old', 'new_string': 'new'},
                'Glob': {'pattern': '*.py', 'path': temp_dir},
                'Grep': {'pattern': 'test'},
                'List': {'path': temp_dir},
                'MultiEdit': {'file_path': test_file_path, 'edits': [{'old_string': 'old', 'new_string': 'new'}]},
                'PythonShell': {'code': 'print("test")'},
                'Read': {'file_path': test_file_path},
                'ToDo': {'todos': []},
                'Write': {'file_path': test_file_path, 'content': 'test'}
            }

            with open(test_file_path, 'w') as f:
                f.write('old')
            for tool in TOOL_LIST:
                with self.subTest(tool=tool.name):
                    args = dummy_args[tool.name]
                    request = CheckedToolRequest(call_id='call_123', tool=tool.name, arguments=args, processed_arguments=tool.check(args))
                    encoded = json.dumps(request, cls=MessageEncoder)
                    decoded = json.loads(encoded, object_hook=message_decoder)

                    self.assertEqual(decoded.call_id, request.call_id)
                    self.assertEqual(decoded.tool, request.tool)
                    self.assertIsNotNone(decoded.processed_arguments)

    def test_tool_response_encode_decode(self):
        for tool in TOOL_LIST:
            with self.subTest(tool=tool.name):
                response = ToolResponse(call_id='call_123', tool=tool.name, response=Text('result'), status=ToolCallStatus.COMPLETED)
                encoded = json.dumps(response, cls=MessageEncoder)
                decoded = json.loads(encoded, object_hook=message_decoder)

                self.assertEqual(response.call_id, decoded.call_id)
                self.assertEqual(response.tool, decoded.tool)
                self.assertEqual(response.status, decoded.status)

    def test_message_tree_encode_decode(self):
        tree = MessageTree(uuid4(), {})
        msg1 = tree.add('user', None, Text('first'))
        msg2 = tree.add('assistant', msg1, ToolRequest(call_id='call_456', tool='BashShell', arguments={'command': 'echo test'}))
        msg3 = tree.add('user', msg2, ToolResponse(call_id='call_456', tool='BashShell', response=Text('test'), status=ToolCallStatus.COMPLETED))

        dumped = tree.dump()
        encoded = json.dumps(dumped, cls=MessageEncoder)
        decoded = json.loads(encoded, object_hook=message_decoder)
        new_tree = MessageTree(uuid4(), {})
        new_tree.load(decoded)

        self.assertEqual(len(new_tree.messages), 3)
        self.assertEqual(new_tree[msg1].content, Text('first'))
        self.assertEqual(new_tree[msg2].content, ToolRequest(call_id='call_456', tool='BashShell', arguments={'command': 'echo test'}))
        self.assertEqual(new_tree[msg3].content, ToolResponse(call_id='call_456', tool='BashShell', response=Text('test'), status=ToolCallStatus.COMPLETED))
