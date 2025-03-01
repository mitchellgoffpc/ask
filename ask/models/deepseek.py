import json
from typing import Any
from ask.models.openai import OpenAIAPI
from ask.models.base import Model, Content, Text, Reasoning, ToolRequest

class DeepseekAPI(OpenAIAPI):
    def render_message(self, role: str, content: list[Content], tool_calls: list[ToolRequest], model: Model) -> dict[str, Any]:
        message = super().render_message(role, content, tool_calls, model)
        if role == 'assistant':  # Deepseek's API requires the assistant's message content to be a single text block
            message['content'] = '\n\n'.join(x['text'] for x in message['content'] if x['type'] == 'text')
        return message

    def result(self, response: dict[str, Any]) -> list[Content]:
        result: list[Content] = []
        for item in response['choices']:
            if item['message'].get('reasoning_content'):
                result.append(Reasoning(text=item['message']['reasoning_content']))
            if item['message'].get('content'):
                result.append(Text(text=item['message']['content']))
            for call in item['message'].get('tool_calls') or []:
                result.append(ToolRequest(call_id=call['id'], tool=call['function']['name'], arguments=json.loads(call['function']['arguments'])))
        return result

    def decode_text_chunk(self, index: int, delta: dict[str, Any]) -> tuple[str, str, str]:
        if delta.get('reasoning_content'):
            assert not delta.get('content'), "'reasoning_content' and 'content' deltas are expected to be mutually exclusive"
            return f"{index}:reasoning", '', delta['reasoning_content']
        elif delta.get('content'):
            return str(index), '', delta['content']
        else:
            return '', '', ''

    def flush_content(self, current_idx: str, next_idx: str, tool: str, data: str) -> tuple[str, Content | None]:
        _, content = super().flush_content(current_idx, next_idx, tool, data)
        if current_idx.endswith(':reasoning'):
            assert not next_idx.endswith(':reasoning'), "Expected reasoning content to be followed by non-reasoning content"
            return '\n</think>\n\n', Reasoning(text=data)
        elif next_idx.endswith(':reasoning'):
            return '<think>\n', content
        else:
            return '', content
