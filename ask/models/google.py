import base64
import json
from typing import Any
from uuid import uuid4

from ask.models.base import API, Model, Tool, Message, Content, Text, Image, ToolRequest, ToolResponse, get_message_groups

class GoogleAPI(API):
    def render_text(self, text: Text) -> dict[str, Any]:
        return {'text': text.text}

    def render_image(self, image: Image) -> dict[str, Any]:
        return {'inline_data': {'mime_type': image.mimetype, 'data': base64.b64encode(image.data).decode()}}

    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]:
        return {'functionCall': {'name': request.tool, 'args': request.arguments}}

    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]:
        return {'functionResponse': {'name': response.tool, 'response': {'result': response.response}}}

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        return {"name": tool.name, "description": tool.description, "parameters": tool.get_input_schema()}

    def render_message(self, role: str, content: list[Content], model: Model) -> dict[str, Any]:
        role = 'model' if role == 'assistant' else role
        return {'role': role, 'parts': [x for c in content for x in self.render_content(c, model)]}

    def url(self, model: Model, stream: bool) -> str:
        return f"{self.base_url}/{model.name}:{'streamGenerateContent?alt=sse' if stream else 'generateContent'}"

    def headers(self, api_key: str) -> dict[str, str]:
        return {"X-goog-api-key": api_key}

    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str, stream: bool) -> dict[str, Any]:
        system_dict = {'system_instruction': {'parts': [{'text': system_prompt}]}} if system_prompt else {}
        tools_dict = {'tools': [{'functionDeclarations': [self.render_tool(tool) for tool in tools]}]} if tools else {}
        msg_dict = {"contents": [self.render_message(role, content, model) for role, content in get_message_groups(messages)]}
        return system_dict | tools_dict | msg_dict

    def result(self, response: dict[str, Any]) -> list[Content]:
        choices = response['candidates']
        assert len(choices) == 1, "Expected exactly one choice"
        result: list[Content] = []
        for content in choices[0]['content']['parts']:
            if 'text' in content:
                result.append(Text(text=content['text']))
            elif 'functionCall' in content:
                result.append(ToolRequest(call_id=str(uuid4()), tool=content['functionCall']['name'], arguments=content['functionCall']['args']))
        return result

    def decode_chunk(self, chunk: str) -> tuple[str, str, str]:
        if not chunk.startswith("data: "):
            return '', '', ''
        line = json.loads(chunk[6:])
        assert len(line['candidates']) == 1, "Expected exactly one choice"
        if 'parts' not in line['candidates'][0]['content']:
            return '', '', ''
        parts = line['candidates'][0]['content']['parts']
        assert len(parts) == 1, "Expected exactly one part"
        if 'text' in parts[0]:
            return '', '', parts[0]['text']
        elif 'functionCall' in parts[0]:
            return '0', f"{parts[0]['functionCall']['name']}:{uuid4()}", json.dumps(parts[0]['functionCall']['args'])
        else:
            raise ValueError(f"Unexpected content part: {parts[0]}")
