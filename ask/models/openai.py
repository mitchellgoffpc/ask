import json
import base64
from typing import Any
from ask.models.base import API, Text, Image, ToolRequest, Message, Tool

class OpenAIAPI(API):
    def render_image(self, mimetype: str, data: bytes) -> dict[str, Any]:
        return {'type': 'image_url', 'image_url': {'url': f'data:{mimetype};base64,{base64.b64encode(data).decode()}'}}

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        params = {p.name: self.render_tool_param(p) for p in tool.parameters}
        required = [p.name for p in tool.parameters if p.required]
        return {
            'type': 'function',
            'function': {
                'name': tool.name,
                'description': tool.description,
                'parameters': {'type': 'object', 'properties': params, 'required': required}}}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def params(self, model_name: str, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        system_msgs = [{"role": "system", "content": system_prompt}] if system_prompt else []
        rendered_msgs = system_msgs + [self.render_message(msg) for msg in messages]
        tools_dict = {"tools": [self.render_tool(tool) for tool in tools]} if tools else {}
        return {"model": model_name, "messages": rendered_msgs, "temperature": temperature, 'max_tokens': 4096, 'stream': self.stream} | tools_dict

    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]:
        result: list[Text | Image | ToolRequest] = []
        for item in response['choices']:
            if item['message'].get('content'):
                result.append(Text(text=item['message']['content']))
            for call in item['message'].get('tool_calls') or []:
                result.append(ToolRequest(tool=call['function']['name'], arguments=json.loads(call['function']['arguments'])))
        return result

    def decode_chunk(self, chunk: str) -> tuple[int | None, str, str]:
        if not chunk.startswith("data: ") or chunk == 'data: [DONE]':
            return None, '', ''
        line = json.loads(chunk[6:])
        assert len(line['choices']) <= 1, f"Expected exactly one choice, but got {len(line['choices'])}!"
        if not line['choices'] or 'delta' not in line['choices'][0]:
            return None, '', ''
        delta = line['choices'][0]['delta']
        if 'tool_calls' in delta:
            assert len(delta['tool_calls']) == 1, f"Expected exactly one tool call, but got {len(delta['tool_calls'])}!"
            tool = delta['tool_calls'][0]['function']
            return line['choices'][0]['index'], tool.get('name', ''), tool['arguments']
        elif delta.get('content'):
            return line['choices'][0]['index'], '', delta['content']
        else:
            return None, '', ''