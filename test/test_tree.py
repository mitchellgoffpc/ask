import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from ask.commands import DocsCommand, FilesCommand
from ask.messages import PDF, Image, Message, Text, ToolCallStatus, ToolRequest, ToolResponse
from ask.tools import TOOL_LIST
from ask.tree import MessageEncoder, MessageTree, message_decoder


class TestMessageTree(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = MessageTree({})

    def test_add(self) -> None:
        msg_uuid = self.tree.add('user', None, Text('hello'))
        assert self.tree[msg_uuid].role == 'user'
        assert self.tree[msg_uuid].content == Text('hello')

    def test_update(self) -> None:
        msg_uuid = self.tree.add('user', None, Text('original'))
        self.tree.update(msg_uuid, Text('updated'))
        assert self.tree[msg_uuid].content == Text('updated')

    def test_clear(self) -> None:
        self.tree.add('user', None, Text('first'))
        self.tree.add('assistant', None, Text('second'))
        self.tree.clear()
        assert len(self.tree.messages) == 0
        assert len(self.tree.parents) == 0

    def test_keys_values(self) -> None:
        msg1 = self.tree.add('user', None, Text('first'))
        msg2 = self.tree.add('assistant', msg1, Text('second'))
        msg3 = self.tree.add('user', msg2, Text('third'))

        keys = self.tree.keys(msg3)
        assert keys == [msg1, msg2, msg3]
        values = self.tree.values(msg2)
        assert values == [Message(role='user', content=Text('first')), Message(role='assistant', content=Text('second'))]
        items = self.tree.items(msg2)
        assert items == [(msg1, Message(role='user', content=Text('first'))), (msg2, Message(role='assistant', content=Text('second')))]


class TestEncoderDecoder(unittest.TestCase):
    def test_image_encode_decode(self) -> None:
        message = Image(mimetype='image/png', data=b'\x89PNG\r\n\x1a\n')
        encoded = json.dumps(message, cls=MessageEncoder)
        decoded = json.loads(encoded, object_hook=message_decoder)
        assert decoded.data == message.data

    def test_pdf_encode_decode(self) -> None:
        message = PDF(name='test.pdf', data=b'%PDF-1.4')
        encoded = json.dumps(message, cls=MessageEncoder)
        decoded = json.loads(encoded, object_hook=message_decoder)
        assert decoded.data == message.data

    def test_tool_request_encode_decode(self) -> None:
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
                'Write': {'file_path': test_file_path, 'content': 'test'},
            }

            with Path(test_file_path).open('w') as f:
                f.write('old')
            for tool in TOOL_LIST:
                with self.subTest(tool=tool.name):
                    args = dummy_args[tool.name]
                    request = ToolRequest(call_id='call_123', tool=tool.name, arguments=args, _artifacts=tool.artifacts(args))
                    encoded = json.dumps(request, cls=MessageEncoder)
                    decoded = json.loads(encoded, object_hook=message_decoder)

                    assert decoded.call_id == request.call_id
                    assert decoded.tool == request.tool
                    assert decoded.artifacts == request.artifacts

    def test_tool_response_encode_decode(self) -> None:
        for tool in TOOL_LIST:
            with self.subTest(tool=tool.name):
                response = ToolResponse(call_id='call_123', tool=tool.name, response=Text('result'), status=ToolCallStatus.COMPLETED)
                encoded = json.dumps(response, cls=MessageEncoder)
                decoded = json.loads(encoded, object_hook=message_decoder)

                assert response.call_id == decoded.call_id
                assert response.tool == decoded.tool
                assert response.status == decoded.status

    def test_command_encode_decode(self) -> None:
        commands = [
            FilesCommand(file_contents={Path('test.txt'): Text('file content')}),
            DocsCommand(file_path=Path('test.txt'), file_contents='file content', prompt_key='some_key'),
        ]
        for command in commands:
            encoded = json.dumps(command, cls=MessageEncoder)
            decoded = json.loads(encoded, object_hook=message_decoder)
            assert decoded == command

    def test_message_tree_encode_decode(self) -> None:
        tree = MessageTree({})
        msg1 = tree.add('user', None, Text('first'))
        msg2 = tree.add('assistant', msg1, ToolRequest(call_id='call_456', tool='BashShell', arguments={'command': 'echo test'}))
        msg3 = tree.add('user', msg2, ToolResponse(call_id='call_456', tool='BashShell', response=Text('test'), status=ToolCallStatus.COMPLETED))

        dumped = tree.dump(msg3)
        new_tree, head = MessageTree.load(dumped)

        assert len(new_tree.messages) == 3
        assert head == msg3
        assert new_tree[msg1].content == Text('first')
        assert new_tree[msg2].content == ToolRequest(call_id='call_456', tool='BashShell', arguments={'command': 'echo test'})
        assert new_tree[msg3].content == ToolResponse(call_id='call_456', tool='BashShell', response=Text('test'), status=ToolCallStatus.COMPLETED)
