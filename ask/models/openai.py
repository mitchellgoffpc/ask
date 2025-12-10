import base64
import json
import socket
from typing import Any

from ask.models.base import API, Model, Tool, Message, Content, Text, Image, PDF, Reasoning, ToolRequest, ToolResponse, Usage, get_message_groups

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
        return {'type': 'reasoning', 'encrypted_content': reasoning.data, 'summary': []}

    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]:
        return {'type': 'function_call', 'call_id': request.call_id, 'name': request.tool, 'arguments': json.dumps(request.arguments)}

    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]:
        match response.response:
            case Text(): content = self.render_text(response.response)
            case Image(): content = self.render_image(response.response)
            case PDF(): content = self.render_pdf(response.response)
        return {'type': 'function_call_output', 'call_id': response.call_id, 'output': [content]}

    def render_message(self, role: str, content: list[Content], model: Model) -> dict[str, Any]:
        return {'role': role, 'content': [x for c in content for x in self.render_content(role, c, model)]}

    def render_message_group(self, role: str, content: list[Content], model: Model) -> list[dict[str, str]]:
        reasoning_msgs = [self.render_reasoning(c) for c in content if isinstance(c, Reasoning)]
        tool_request_msgs = [self.render_tool_request(c) for c in content if isinstance(c, ToolRequest)]
        tool_response_msgs = [self.render_tool_response(c) for c in content if isinstance(c, ToolResponse)]
        other_content: list[Content] = [c for c in content if not isinstance(c, (Reasoning, ToolRequest, ToolResponse))]
        other_messages = [self.render_message(role, other_content, model)] if other_content else []
        return reasoning_msgs + tool_request_msgs + tool_response_msgs + other_messages

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        return {'type': 'function', 'name': tool.name, 'description': tool.description, 'parameters': tool.get_input_schema()}

    def render_system_prompt(self, system_prompt: str, model: Model) -> list[dict[str, str]]:
        if not system_prompt:
            return []
        elif not model.supports_system_prompt:
            return [{'role': 'user', 'content': system_prompt}, {'role': 'assistant', 'content': 'Understood.'}]
        else:
            return [{'role': 'system', 'content': system_prompt}]

    def headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str, stream: bool) -> dict[str, Any]:
        cache_key = f'ask-{socket.gethostname()}'
        tool_defs = [self.render_tool(tool) for tool in tools]
        system_msgs = self.render_system_prompt(system_prompt, model)
        chat_msgs = [msg for role, group in get_message_groups(messages) for msg in self.render_message_group(role, group, model)]
        metadata = {"prompt_cache_key": cache_key, "store": False} | ({"include": ["reasoning.encrypted_content"]} if model.supports_reasoning else {})
        return {"model": model.name, "input": system_msgs + chat_msgs, "stream": stream, "tools": tool_defs, **metadata}

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
