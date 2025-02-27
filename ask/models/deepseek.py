import json
from typing import Any, Iterator
from ask.models.openai import OpenAIAPI
from ask.models.base import Text, Image, ToolRequest

class DeepseekAPI(OpenAIAPI):
    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]:
        result: list[Text | Image | ToolRequest] = []
        for item in response['choices']:
            if item['message'].get('content'):
                content = item['message']['content']
                if item['message'].get('reasoning_content'):
                    content = f"<think>\n{item['message']['reasoning_content']}\n</think>\n\n{content}"
                result.append(Text(text=content))
            for call in item['message'].get('tool_calls') or []:
                result.append(ToolRequest(tool=call['function']['name'], arguments=json.loads(call['function']['arguments'])))
        return result

    def decode(self, chunks: Iterator[str]) -> Iterator[tuple[str, Text | Image | ToolRequest | None]]:
        reasoning = False
        for chunk in chunks:
            if chunk.startswith("data: ") and chunk != 'data: [DONE]':
                line = json.loads(chunk[6:])
                delta = line['choices'][0]['delta']
                next_reasoning = bool(delta.get('reasoning_content'))
                if not reasoning and next_reasoning:
                    yield '<think>\n', None
                if reasoning and not next_reasoning:
                    yield '\n</think>\n\n', None
                reasoning = next_reasoning
                content = delta.get('content') or delta.get('reasoning_content') or ''
                yield content, None
