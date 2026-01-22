import base64
import json
from typing import Any
from uuid import uuid4

from ask.messages import Message, Content, Text, Image, PDF, Reasoning, ToolDescriptor, ToolRequest, ToolResponse, Usage, SystemPrompt
from ask.models.base import API, Model, get_message_groups

class GoogleAPI(API):
    def render_text(self, text: Text) -> dict[str, Any]:
        return {'text': text.text}

    def render_image(self, image: Image) -> dict[str, Any]:
        return {'inline_data': {'mime_type': image.mimetype, 'data': base64.b64encode(image.data).decode()}}

    def render_pdf(self, pdf: PDF) -> dict[str, Any]:
        return {'inline_data': {'mime_type': 'application/pdf', 'data': base64.b64encode(pdf.data).decode()}}

    def render_reasoning(self, reasoning: Reasoning) -> dict[str, Any]:
        raise NotImplementedError("Google API does not support reasoning")

    def render_tool_request(self, request: ToolRequest) -> dict[str, Any]:
        return {'functionCall': {'name': request.tool, 'args': request.arguments}}

    def render_tool_response(self, response: ToolResponse) -> dict[str, Any]:
        assert isinstance(response.response, Text)
        return {'functionResponse': {'name': response.tool, 'response': {'result': response.response.text}}}

    def render_tool_descriptor(self, tool: ToolDescriptor) -> dict[str, Any]:
        return {"name": tool.name, "description": tool.description, "parameters": tool.input_schema}

    def render_system_prompt(self, system_prompt: SystemPrompt, model: Model) -> list[dict[str, Any]]:
        return [self.render_text(Text(system_prompt.text))]

    def render_messages(self, messages: list[Message], model: Model) -> dict[str, Any]:
        system, tools, msgs = [], [], []
        for role, group in get_message_groups(messages):
            content = []
            for c in group:
                match c:
                    case SystemPrompt(): system.extend(self.render_system_prompt(c, model))
                    case ToolDescriptor(): tools.append(self.render_tool_descriptor(c))
                    case _: content.extend(self.render_content(role, c, model))
            msgs.append({'role': 'model' if role == 'assistant' else role, 'parts': content})
        return {'system_instruction': {'parts': system}, 'tools': [{'functionDeclarations': tools}], 'contents': msgs}

    def url(self, model: Model, stream: bool) -> str:
        return f"{self.base_url}/{model.name}:{'streamGenerateContent?alt=sse' if stream else 'generateContent'}"

    def headers(self, api_key: str) -> dict[str, str]:
        return {"X-goog-api-key": api_key}

    def params(self, model: Model, messages: list[Message], stream: bool) -> dict[str, Any]:
        return self.render_messages(messages, model)

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

    def decode_chunk(self, chunk: str) -> tuple[str, str, str, Usage | None]:
        if not chunk.startswith("data: "):
            return '', '', '', None
        line = json.loads(chunk[6:])
        assert len(line['candidates']) == 1, "Expected exactly one choice"
        if 'parts' not in line['candidates'][0]['content']:
            return '', '', '', None
        parts = line['candidates'][0]['content']['parts']
        assert len(parts) == 1, "Expected exactly one part"
        if 'text' in parts[0]:
            return '0', '', parts[0]['text'], None
        elif 'functionCall' in parts[0]:
            return str(uuid4()), f"{parts[0]['functionCall']['name']}:{uuid4()}", json.dumps(parts[0]['functionCall']['args']), None
        else:
            raise ValueError(f"Unexpected content part: {parts[0]}")
