import json
from typing import Any, Iterator
from ask.models.openai import OpenAIAPI
from ask.models.base import Text, Image, ToolRequest

class DeepseekAPI(OpenAIAPI):
    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]:
        assert len(response['choices']) == 1, f"Expected exactly one choice, but got {len(response['choices'])}!"
        message = response['choices'][0]['message']
        content = message['content']
        if message.get('reasoning_content'):
            content = f"<think>\n{message['reasoning_content']}\n</think>\n\n{content}"
        return [Text(text=content)]

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