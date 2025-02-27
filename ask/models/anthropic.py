import json
import base64
from typing import Any
from ask.models.base import API, Message, Tool, Text, Image, ToolRequest

class AnthropicAPI(API):
    def render_image(self, mimetype: str, data: bytes) -> dict[str, Any]:
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': mimetype, 'data': base64.b64encode(data).decode()}}

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        params = {p.name: self.render_tool_param(p) for p in tool.parameters}
        required = [p.name for p in tool.parameters if p.required]
        return {"name": tool.name, "description": tool.description, "input_schema": {'type': 'object', 'properties': params, 'required': required}}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-api-key": api_key, 'anthropic-version': '2023-06-01'}

    def params(self, model_name: str, messages: list[Message], tools: list[Tool], system_prompt: str = '',
               stream: bool = True, temperature: float = 0.7) -> dict[str, Any]:
        rendered_msgs = [self.render_message(msg) for msg in messages]
        system_dict = {'system': system_prompt} if system_prompt else {}
        tools_dict = {'tools': [self.render_tool(tool) for tool in tools]} if tools else {}
        msg_dict = {"model": model_name, "messages": rendered_msgs, "temperature": temperature, 'max_tokens': 4096, 'stream': stream}
        return system_dict | tools_dict | msg_dict

    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]:
        result: list[Text | Image | ToolRequest] = []
        for item in response['content']:
            if item['type'] == 'text':
                result.append(Text(text=item['text']))
            elif item['type'] == 'tool_use':
                result.append(ToolRequest(tool=item['name'], arguments=item['input']))
        return result

    def decode_chunk(self, chunk: str) -> tuple[int | None, str, str]:
        if not chunk.startswith("data: ") or chunk == 'data: [DONE]':
            return None, '', ''
        line = json.loads(chunk[6:])
        if line['type'] == 'content_block_start' and line['content_block']['type'] == 'tool_use':
            assert not line['content_block']['input'], "Expected no input for content_block_start"
            return line['index'], line['content_block']['name'], ''
        elif line['type'] == 'content_block_delta':
            if line['delta']['type'] == 'input_json_delta':
                return line['index'], '', line['delta']['partial_json']
            elif line['delta']['type'] == 'text_delta':
                return line['index'], '', line['delta']['text']
        return None, '', ''
