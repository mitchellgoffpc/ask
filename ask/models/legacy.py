import base64
import json
from typing import Any

from ask.messages import Message, Content, Text, Image, PDF, Reasoning, ToolDescriptor, ToolRequest, ToolResponse, Usage, SystemPrompt
from ask.models.base import API, Model, get_message_groups

class LegacyOpenAIAPI(API):
    def render_text(self, text: Text) -> dict[str, Any]:
        return {'type': 'text', 'text': text.text}

    def render_reasoning(self, reasoning: Reasoning) -> dict[str, Any]:
        return {'type': 'reasoning', 'reasoning': reasoning.data}

    def render_image(self, image: Image) -> dict[str, Any]:
        return {'type': 'image_url', 'image_url': {'url': f'data:{image.mimetype};base64,{base64.b64encode(image.data).decode()}'}}

    def render_pdf(self, pdf: PDF) -> dict[str, Any]:
        raise NotImplementedError("PDF rendering not supported in Legacy OpenAI API")

    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]:
        return {'id': request.call_id, 'type': 'function', 'function': {'name': request.tool, 'arguments': json.dumps(request.arguments)}}

    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]:
        assert isinstance(response.response, Text)
        return {'role': 'tool', 'tool_call_id': response.call_id, 'content': response.response.text}

    def render_tool_descriptor(self, tool: ToolDescriptor) -> dict[str, Any]:
        return {'type': 'function', 'function': {'name': tool.name, 'description': tool.description, 'parameters': tool.input_schema}}

    def render_system_prompt(self, system_prompt: SystemPrompt, model: Model) -> list[dict[str, Any]]:
        if not model.capabilities.system_prompt:
            return [{'role': 'user', 'content': system_prompt.text}, {'role': 'assistant', 'content': 'Understood.'}]
        else:
            return [{'role': 'system', 'content': system_prompt.text}]

    def render_messages(self, messages: list[Message], model: Model) -> dict[str, Any]:
        tools, msgs = [], []
        for role, group in get_message_groups(messages):
            content, tool_requests = [], []
            for c in group:
                match c:
                    case SystemPrompt(): msgs.extend(self.render_system_prompt(c, model))
                    case ToolDescriptor(): tools.append(self.render_tool_descriptor(c))
                    case ToolRequest(): tool_requests.append(self.render_tool_request(c))
                    case ToolResponse(): msgs.append(self.render_tool_response(c))
                    case _: content.extend(self.render_content(role, c, model))
            msgs.append({'role': role} | ({'content': content} if content else {}) | ({'tool_calls': tool_requests} if tool_requests else {}))
        return {'tools': tools, 'messages': msgs}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def params(self, model: Model, messages: list[Message], stream: bool) -> dict[str, Any]:
        return {"model": model.name, "temperature": 1.0, 'stream': stream} | self.render_messages(messages, model)

    def result(self, response: dict[str, Any]) -> list[Content]:
        result: list[Content] = []
        for item in response['choices']:
            if item['message'].get('reasoning'):
                result.append(Reasoning(data=item['message']['reasoning'], encrypted=True))
            if item['message'].get('content'):
                result.append(Text(text=item['message']['content']))
            for call in item['message'].get('tool_calls') or []:
                result.append(ToolRequest(call_id=call['id'], tool=call['function']['name'], arguments=json.loads(call['function']['arguments'])))
        return result

    def decode_chunk(self, chunk: str) -> tuple[str, str, str, Usage | None]:
        if not chunk.startswith("data: ") or chunk == 'data: [DONE]':
            return '', '', '', None
        line = json.loads(chunk[6:])
        if 'choices' not in line:
            return '', '', '', None
        assert len(line['choices']) <= 1, f"Expected exactly one choice, but got {len(line['choices'])}!"
        if not line['choices'] or 'delta' not in line['choices'][0]:
            return '', '', '', None
        index = line['choices'][0]['index']
        delta = line['choices'][0]['delta']
        if 'tool_calls' in delta:
            assert len(delta['tool_calls']) == 1, f"Expected exactly one tool call, but got {len(delta['tool_calls'])}!"
            return self.decode_tool_chunk(index, delta)
        else:
            return self.decode_text_chunk(index, delta)

    def decode_tool_chunk(self, index: int, delta: dict[str, Any]) -> tuple[str, str, str, Usage | None]:
        tool = delta['tool_calls'][0]['function']
        tool_name = f"{tool['name']}:{delta['tool_calls'][0]['id']}" if 'name' in tool else ''
        subindex = f"{index}.{delta['tool_calls'][0]['index']}"
        return subindex, tool_name, tool['arguments'], None

    def decode_text_chunk(self, index: int, delta: dict[str, Any]) -> tuple[str, str, str, Usage | None]:
        if delta.get('content'):
            return str(index), '', delta['content'], None
        else:
            return '', '', '', None
