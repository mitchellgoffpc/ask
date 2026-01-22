from ask.messages import Message, Text, Image, Reasoning, ToolRequest, ToolResponse, Usage, ToolCallStatus, SystemPrompt, ToolDescriptor

INPUT_MESSAGES = [
    Message('user', SystemPrompt('System prompt')),
    Message('user', ToolDescriptor('test_tool', 'A test tool', {'type': 'object', 'properties': {}})),
    Message('user', Text('Hello')),
    Message('assistant', Reasoning(data='i should say hi', encrypted=True, summary='say hello')),
    Message('assistant', Text('Hi')),
    Message('assistant', ToolRequest('call_1', 'test_tool', {'arg': 'value'})),
    Message('user', ToolResponse('call_1', 'test_tool', Text('result'), ToolCallStatus.COMPLETED)),
    Message('user', Image('image/png', b'fakeimagedata'))]

RESULT_OUTPUT = [
    Reasoning(data='encrypted', encrypted=True),
    Text(text='Hello world'),
    ToolRequest(call_id='c1', tool='tool', arguments={'foo': 'bar'}),
    Usage(input=100, cache_read=20, cache_write=0, output=50)]

DECODE_OUTPUT = (
    [('', x) for x in RESULT_OUTPUT[:1]] +
    [('Hello', None), (' world', None)] +
    [('', x) for x in RESULT_OUTPUT[1:]])

async def to_async(data):
    for item in data:
        yield item
