import base64
import json
from typing import Any

from ask.models.base import API, Model, Tool, Message, Content, Text, Image, ToolRequest, ToolResponse

class AnthropicAPI(API):
    def render_image(self, image: Image) -> dict[str, Any]:
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': image.mimetype, 'data': base64.b64encode(image.data).decode()}}

    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]:
        return {'type': 'tool_use', 'id': request.call_id, 'name': request.tool, 'input': request.arguments}

    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]:
        return {'type': 'tool_result', 'tool_use_id': response.call_id, 'content': response.response}

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        return {"name": tool.name, "description": tool.description, "input_schema": tool.get_input_schema()}

    def render_message(self, message: Message, model: Model) -> dict[str, Any]:
        return {'role': message.role, 'content': [self.render_content(x, model) for x in message.content]}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-api-key": api_key, 'anthropic-version': '2023-06-01'}

    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        assert model.supports_system_prompt and model.supports_tools, "Wtf? All anthropic models support system prompts and tools."
        chat_msgs = [self.render_message(msg, model) for msg in messages]
        system_dict = {'system': system_prompt} if system_prompt else {}
        tools_dict = {'tools': [self.render_tool(tool) for tool in tools]} if tools else {}
        msg_dict = {"model": model.name, "messages": chat_msgs, "temperature": temperature, 'max_tokens': 4096, 'stream': model.stream}
        return system_dict | tools_dict | msg_dict

    def result(self, response: dict[str, Any]) -> list[Content]:
        result: list[Content] = []
        for content in response['content']:
            if content['type'] == 'text':
                result.append(Text(text=content['text']))
            elif content['type'] == 'tool_use':
                result.append(ToolRequest(call_id=content['id'], tool=content['name'], arguments=content['input']))
        return result

    def decode_chunk(self, chunk: str) -> tuple[str, str, str]:
        if not chunk.startswith("data: ") or chunk == 'data: [DONE]':
            return '', '', ''
        line = json.loads(chunk[6:])
        if line['type'] == 'content_block_start' and line['content_block']['type'] == 'tool_use':
            assert not line['content_block']['input'], "Expected no input for content_block_start"
            tool_name = f"{line['content_block']['name']}:{line['content_block']['id']}"
            return str(line['index']), tool_name, ''
        elif line['type'] == 'content_block_delta':
            if line['delta']['type'] == 'input_json_delta':
                return str(line['index']), '', line['delta']['partial_json']
            elif line['delta']['type'] == 'text_delta':
                return str(line['index']), '', line['delta']['text']
        return '', '', ''
