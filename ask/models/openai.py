import json
import base64
from typing import Any
from ask.tools.render import render_tools_prompt
from ask.models.base import API, Model, Text, Image, ToolRequest, Message, Tool

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

    def render_system_prompt(self, system_prompt: str, model: Model) -> list[dict[str, str]]:
        if not system_prompt:
            return []
        elif not model.supports_system_prompt:
            return [{'role': 'user', 'content': system_prompt}, {'role': 'assistant', 'content': 'Understood.'}]
        else:
            return [{'role': 'system', 'content': system_prompt}]

    def headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        if not model.supports_tools:
            system_prompt = f"{system_prompt}\n\n{render_tools_prompt(tools)}".strip()
        rendered_msgs = self.render_system_prompt(system_prompt, model) + [self.render_message(msg, model) for msg in messages]
        tools_dict = {"tools": [self.render_tool(tool) for tool in tools]} if tools and model.supports_tools else {}
        return {"model": model.name, "messages": rendered_msgs, "temperature": temperature, 'max_tokens': 4096, 'stream': model.stream} | tools_dict

    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]:
        result: list[Text | Image | ToolRequest] = []
        for item in response['choices']:
            if item['message'].get('content'):
                result.append(Text(text=item['message']['content']))
            for call in item['message'].get('tool_calls') or []:
                result.append(ToolRequest(tool=call['function']['name'], arguments=json.loads(call['function']['arguments'])))
        return result

    def decode_chunk(self, chunk: str) -> tuple[str, str, str]:
        if not chunk.startswith("data: ") or chunk == 'data: [DONE]':
            return '', '', ''
        line = json.loads(chunk[6:])
        assert len(line['choices']) <= 1, f"Expected exactly one choice, but got {len(line['choices'])}!"
        if not line['choices'] or 'delta' not in line['choices'][0]:
            return '', '', ''
        index = line['choices'][0]['index']
        delta = line['choices'][0]['delta']
        if 'tool_calls' in delta:
            assert len(delta['tool_calls']) == 1, f"Expected exactly one tool call, but got {len(delta['tool_calls'])}!"
            return self.decode_tool_chunk(index, delta)
        else:
            return self.decode_text_chunk(index, delta)

    def decode_tool_chunk(self, index: int, delta: dict[str, Any]) -> tuple[str, str, str]:
        tool = delta['tool_calls'][0]['function']
        subindex = f"{index}.{delta['tool_calls'][0]['index']}"
        return subindex, tool.get('name', ''), tool['arguments']

    def decode_text_chunk(self, index: int, delta: dict[str, Any]) -> tuple[str, str, str]:
        if delta.get('content'):
            return str(index), '', delta['content']
        else:
            return '', '', ''


class O1API(OpenAIAPI):
    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        if not model.supports_tools:
            system_prompt = f"{system_prompt}\n\n{render_tools_prompt(tools)}".strip()
        rendered_msgs = self.render_system_prompt(system_prompt, model) + [self.render_message(msg, model) for msg in messages]
        tools_dict = {"tools": [self.render_tool(tool) for tool in tools]} if tools and model.supports_tools else {}
        return {"model": model.name, "messages": rendered_msgs, 'stream': model.stream} | tools_dict
