import base64
import json
import socket
from typing import Any

from ask.messages import Message, Content, Text, Image, PDF, Reasoning, ToolDescriptor, ToolRequest, ToolResponse, Usage, SystemPrompt
from ask.models.base import API, Model, get_message_groups

class OpenAIAPI(API):
    def render_text(self, text: Text) -> dict[str, Any]:
        return {'type': 'input_text', 'text': text.text}

    def render_response_text(self, text: Text) -> dict[str, Any]:
        return {'type': 'output_text', 'text': text.text}

    def render_image(self, image: Image) -> dict[str, Any]:
        return {'type': 'input_image', 'image_url': f'data:{image.mimetype};base64,{base64.b64encode(image.data).decode()}'}

    def render_pdf(self, pdf: PDF) -> dict[str, Any]:
        return {'type': 'input_file', 'filename': pdf.name, 'file_data': f'data:application/pdf;base64,{base64.b64encode(pdf.data).decode()}'}

    def render_reasoning(self, reasoning: Reasoning) -> dict[str, Any]:
        return {'type': 'reasoning', 'encrypted_content': reasoning.data, 'summary': [reasoning.summary] if reasoning.summary else []}

    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]:
        return {'type': 'function_call', 'call_id': request.call_id, 'name': request.tool, 'arguments': json.dumps(request.arguments)}

    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]:
        match response.response:
            case Text(): content = self.render_text(response.response)
            case Image(): content = self.render_image(response.response)
            case PDF(): content = self.render_pdf(response.response)
        return {'type': 'function_call_output', 'call_id': response.call_id, 'output': [content]}

    def render_tool_descriptor(self, tool: ToolDescriptor) -> dict[str, Any]:
        return {'type': 'function', 'name': tool.name, 'description': tool.description, 'parameters': tool.input_schema}

    def render_system_prompt(self, system_prompt: SystemPrompt, model: Model) -> list[dict[str, Any]]:
        if model.capabilities.system_prompt:
            return [{'role': 'system', 'content': system_prompt.text}]
        else:
            return [{'role': 'user', 'content': [self.render_text(Text(system_prompt.text))]},
                    {'role': 'assistant', 'content': [self.render_response_text(Text("Understood."))]}]

    def render_messages(self, messages: list[Message], model: Model) -> dict[str, Any]:
        tools, msgs = [], []
        for role, group in get_message_groups(messages):
            content, tool_calls = [], []
            for c in group:
                match c:
                    case SystemPrompt(): msgs.extend(self.render_system_prompt(c, model))
                    case ToolDescriptor(): tools.append(self.render_tool_descriptor(c))
                    case ToolRequest(): tool_calls.append(self.render_tool_request(c))
                    case ToolResponse(): msgs.append(self.render_tool_response(c))
                    case Reasoning(): msgs.append(self.render_reasoning(c))
                    case _: content.extend(self.render_content(role, c, model))
            if content:
                msgs.append({'role': role, 'content': content})
            if tool_calls:
                msgs.extend(tool_calls)
        return {'tools': tools, 'input': msgs}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def params(self, model: Model, messages: list[Message], stream: bool) -> dict[str, Any]:
        cache_key = f'ask-{socket.gethostname()}'
        metadata = {"prompt_cache_key": cache_key, "store": False} | ({"include": ["reasoning.encrypted_content"]} if model.capabilities.reasoning else {})
        return {"model": model.name, "stream": stream} | metadata | self.render_messages(messages, model)

    def result(self, response: dict[str, Any]) -> list[Content]:
        result: list[Content] = []
        for msg in response['output']:
            if msg['type'] == 'message':
                for item in msg['content']:
                    if item['type'] == 'output_text':
                        result.append(Text(text=item['text']))
            elif msg['type'] == 'reasoning':
                result.append(Reasoning(data=msg['encrypted_content'], encrypted=True))
            elif msg['type'] == 'function_call':
                result.append(ToolRequest(call_id=msg['call_id'], tool=msg['name'], arguments=json.loads(msg['arguments'])))
        return [*result, self.decode_usage(response['usage'])]

    def decode_chunk(self, chunk: str) -> tuple[str, str, str, Usage | None]:
        if not chunk.startswith("data: "):
            return '', '', '', None
        line = json.loads(chunk[6:])
        usage = self.decode_usage(line['response']['usage']) if line.get('response', {}).get('usage') else None
        if line['type'] == 'response.output_item.added' and line.get('item', {}).get('type') == 'function_call':
            return str(line['output_index']), f"{line['item']['name']}:{line['item']['call_id']}", line['item']['arguments'], usage
        elif line['type'] == 'response.function_call_arguments.delta':
            return str(line['output_index']), '', line['delta'], usage
        elif line['type'] == 'response.output_text.delta':
            return str(line['output_index']), '', line['delta'], usage
        elif line['type'] == 'response.output_item.done' and line.get('item', {}).get('type') == 'reasoning':
            return str(line['output_index']), '/reasoning:encrypted', line['item']['encrypted_content'], usage
        else:
            return '', '', '', usage

    def decode_usage(self, usage: dict[str, Any]) -> Usage:
        return Usage(
            input=usage['input_tokens'],
            cache_write=0,
            cache_read=usage['input_tokens_details']['cached_tokens'],
            output=usage['output_tokens'])
