import base64
import json
from typing import Any

from ask.messages import Message, Content, Text, Image, PDF, Reasoning, ToolDescriptor, ToolRequest, ToolResponse, Usage, SystemPrompt
from ask.models.base import API, Model, get_message_groups

class AnthropicAPI(API):
    supports_image_tools: bool = True

    def render_text(self, text: Text) -> dict[str, Any]:
        return {'type': 'text', 'text': text.text}

    def render_image(self, image: Image) -> dict[str, Any]:
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': image.mimetype, 'data': base64.b64encode(image.data).decode()}}

    def render_pdf(self, pdf: PDF) -> dict[str, Any]:
        return {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': base64.b64encode(pdf.data).decode()}}

    def render_reasoning(self, reasoning: Reasoning) -> dict[str, Any]:
        return {'type': 'thinking', 'signature': reasoning.data, 'thinking': reasoning.summary or ''}

    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]:
        return {'type': 'tool_use', 'id': request.call_id, 'name': request.tool, 'input': request.arguments}

    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]:
        match response.response:
            case Text(): content = self.render_text(response.response)
            case Image(): content = self.render_image(response.response)
            case PDF(): content = self.render_pdf(response.response)
        return {'type': 'tool_result', 'tool_use_id': response.call_id, 'content': [content]}

    def render_tool_descriptor(self, tool: ToolDescriptor) -> dict[str, Any]:
        return {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}

    def render_system_prompt(self, system_prompt: SystemPrompt, model: Model) -> list[dict[str, Any]]:
        return [{'type': 'text', 'text': system_prompt.text, 'cache_control': {'type': 'ephemeral'}}]

    def render_messages(self, messages: list[Message], model: Model) -> dict[str, Any]:
        system, tools, msgs = [], [], []
        for role, group in get_message_groups(messages):
            content = []
            for c in group:
                match c:
                    case SystemPrompt(): system.extend(self.render_system_prompt(c, model))
                    case ToolDescriptor(): tools.append(self.render_tool_descriptor(c))
                    case _: content.extend(self.render_content(role, c, model))
            msgs.append({'role': role, 'content': content})
        if msgs:
            msgs[-1]['content'][-1]['cache_control'] = {'type': 'ephemeral'}  # type: ignore[index]
        return {'system': system, 'tools': tools, 'messages': msgs}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-api-key": api_key, 'anthropic-version': '2023-06-01'}

    def params(self, model: Model, messages: list[Message], stream: bool) -> dict[str, Any]:
        assert model.supports_system_prompt, "Wtf? All anthropic models support system prompts."
        # reasoning = {'thinking': {"type": "enabled", "budget_tokens": 1024}} if model.supports_reasoning else {}
        return {"model": model.name, "temperature": 1.0, 'max_tokens': 4096, 'stream': stream} | self.render_messages(messages, model)

    def result(self, response: dict[str, Any]) -> list[Content]:
        result: list[Content] = []
        for content in response['content']:
            if content['type'] == 'text':
                result.append(Text(text=content['text']))
            elif content['type'] == 'thinking':
                result.append(Reasoning(data=content['signature'], summary=content['thinking'], encrypted=True))
            elif content['type'] == 'tool_use':
                result.append(ToolRequest(call_id=content['id'], tool=content['name'], arguments=content['input']))
        return [*result, self.decode_usage(response['usage'])]

    def decode_chunk(self, chunk: str) -> tuple[str, str, str, Usage | None]:
        if not chunk.startswith("data: ") or chunk == 'data: [DONE]':
            return '', '', '', None
        line = json.loads(chunk[6:])
        usage = self.decode_usage(line['usage']) if 'usage' in line else None
        if line['type'] == 'content_block_start' and line['content_block']['type'] == 'tool_use':
            assert not line['content_block']['input'], "Expected no input for content_block_start"
            tool_name = f"{line['content_block']['name']}:{line['content_block']['id']}"
            return str(line['index']), tool_name, '', usage
        elif line['type'] == 'content_block_delta':
            if line['delta']['type'] == 'input_json_delta':
                return str(line['index']), '', line['delta']['partial_json'], usage
            elif line['delta']['type'] == 'text_delta':
                return str(line['index']), '', line['delta']['text'], usage
            elif line['delta']['type'] == 'thinking_delta':
                return str(line['index']), '/reasoning:encrypted', line['delta']['thinking'] + '\x00', usage
            elif line['delta']['type'] == 'signature_delta':
                return str(line['index']), '/reasoning:encrypted', '\x00' + line['delta']['signature'], usage
        return '', '', '', usage

    def decode_usage(self, usage: dict[str, Any]) -> Usage:
        return Usage(
            input=usage['input_tokens'],
            cache_write=usage['cache_creation_input_tokens'],
            cache_read=usage['cache_read_input_tokens'],
            output=usage['output_tokens'])
