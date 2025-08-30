import base64
import json
from typing import Any

from ask.models.tool_helpers import render_tools_prompt, render_tool_request, render_tool_response
from ask.models.base import API, Model, Tool, Message, Content, Text, Image, ToolRequest, ToolResponse, get_message_groups

class LegacyOpenAIAPI(API):
    def render_text(self, text: Text) -> dict[str, Any]:
        return {'type': 'text', 'text': text.text}

    def render_image(self, image: Image) -> dict[str, Any]:
        return {'type': 'image_url', 'image_url': {'url': f'data:{image.mimetype};base64,{base64.b64encode(image.data).decode()}'}}

    # render_tool_request / render_tool_response are only used as fallbacks for models that don't support tool calls
    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]:
        return {'type': 'text', 'text': render_tool_request(request)}

    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]:
        return {'type': 'text', 'text': render_tool_response(response)}

    # render_tool_call / render_tool_message are the primary methods for rendering tool calls for the OpenAI schema
    def render_tool_call(self, request: ToolRequest) -> dict[str, Any]:
        return {'id': request.call_id, 'type': 'function', 'function': {'name': request.tool, 'arguments': json.dumps(request.arguments)}}

    def render_tool_message(self, response: ToolResponse) -> dict[str, Any]:
        return {'role': 'tool', 'tool_call_id': response.call_id, 'content': response.response}

    def render_message(self, role: str, content: list[Content], tool_calls: list[ToolRequest], model: Model) -> dict[str, Any]:
        tool_call_dict = {'tool_calls': [self.render_tool_call(x) for x in tool_calls]} if tool_calls else {}
        rendered_content = [x for c in content for x in self.render_content(c, model)]
        # NOTE: This is required by cerebras, but I'm pretty sure this doesn't match the OpenAI schema
        if role == 'assistant':
            assert all(c['type'] == 'text' for c in rendered_content), "Assistant messages must only contain text"
            return {'role': role, 'content': '\n\n'.join(c['text'] for c in rendered_content)} | tool_call_dict
        return {'role': role, 'content': rendered_content} | tool_call_dict

    def render_message_group(self, role: str, content: list[Content], model: Model) -> list[dict[str, str]]:
        # OpenAI's Legacy API has tools as a separate role, so we need to split them out into a separate message for each tool call
        if model.supports_tools:
            tool_response_msgs = [self.render_tool_message(c) for c in content if isinstance(c, ToolResponse)]
            tool_requests = [c for c in content if isinstance(c, ToolRequest)]
            other_content: list[Content] = [c for c in content if not isinstance(c, (ToolRequest, ToolResponse))]
            other_messages = [self.render_message(role, other_content, tool_requests, model)] if other_content or tool_requests else []
            return tool_response_msgs + other_messages
        else:
            return [self.render_message(role, content, [], model)]

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {'name': tool.name, 'description': tool.description, 'parameters': tool.get_input_schema()}}

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
        system_msgs = self.render_system_prompt(system_prompt, model)
        chat_msgs = [msg for role, group in get_message_groups(messages) for msg in self.render_message_group(role, group, model)]
        msg_dict = {"model": model.name, "messages": system_msgs + chat_msgs, "temperature": temperature, 'stream': model.stream}
        tools_dict = {"tools": [self.render_tool(tool) for tool in tools]} if tools and model.supports_tools else {}
        return msg_dict | tools_dict

    def result(self, response: dict[str, Any]) -> list[Content]:
        result: list[Content] = []
        for item in response['choices']:
            if item['message'].get('content'):
                result.append(Text(text=item['message']['content']))
            for call in item['message'].get('tool_calls') or []:
                result.append(ToolRequest(call_id=call['id'], tool=call['function']['name'], arguments=json.loads(call['function']['arguments'])))
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
        tool_name = f"{tool['name']}:{delta['tool_calls'][0]['id']}" if 'name' in tool else ''
        subindex = f"{index}.{delta['tool_calls'][0]['index']}"
        return subindex, tool_name, tool['arguments']

    def decode_text_chunk(self, index: int, delta: dict[str, Any]) -> tuple[str, str, str]:
        if delta.get('content'):
            return str(index), '', delta['content']
        else:
            return '', '', ''
