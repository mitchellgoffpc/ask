import json
from typing import Any
from dataclasses import dataclass

Prompt = list[dict[str, str]]

@dataclass
class API:
    key: str
    url: str

    def headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def params(self, model_name: str, messages: Prompt, system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}, *messages]
        return {"model": model_name, "messages": messages, "temperature": temperature, 'max_tokens': 4096, 'stream': True}

    def result(self, response: dict[str, Any]) -> str:
        assert len(response['choices']) == 1, f"Expected exactly one choice, but got {len(response['choices'])}!"
        return response['choices'][0]['message']['content']

    def decode(self, chunk: str) -> str:
        if chunk.startswith("data: ") and chunk != 'data: [DONE]':
            line = json.loads(chunk[6:])
            return line['choices'][0]['delta'].get('content', '')
        else:
            return ''

class AnthropicAPI(API):
    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-api-key": api_key, 'anthropic-version': '2023-06-01'}

    def params(self, model_name: str, messages: Prompt, system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        system = {'system': system_prompt} if system_prompt else {}
        return {"model": model_name, "messages": messages, "temperature": temperature, 'max_tokens': 4096, 'stream': True} | system

    def result(self, response: dict[str, Any]) -> str:
        assert len(response['content']) == 1, f"Expected exactly one choice, but got {len(response['content'])}!"
        return response['content'][0]['text']

    def decode(self, chunk: str) -> str:
        if chunk.startswith("data: ") and chunk != 'data: [DONE]':
            line = json.loads(chunk[6:])
            if line['type'] == 'content_block_delta':
                return line['delta']['text']
        return ''

@dataclass
class Model:
    name: str
    api: API
    shortcuts: list[str]


APIS = {
    'openai': API(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY'),
    'mistral': API(url='https://api.mistral.ai/v1/chat/completions', key='MISTRAL_API_KEY'),
    'groq': API(url='https://api.groq.com/openai/v1/chat/completions', key='GROQ_API_KEY'),
    'anthropic': AnthropicAPI(url='https://api.anthropic.com/v1/messages', key='ANTHROPIC_API_KEY'),
}

MODELS = [
    Model(name='gpt-3.5-turbo', api=APIS['openai'], shortcuts=['gpt3', '3']),
    Model(name='gpt-4', api=APIS['openai'], shortcuts=['gpt4', '4']),
    Model(name='gpt-4-turbo', api=APIS['openai'], shortcuts=['gpt4t', '4t', 't']),
    Model(name='gpt-4o-mini', api=APIS['openai'], shortcuts=['gpt4o-mini', 'gpt4om', 'gpt4m', '4m']),
    Model(name='gpt-4o', api=APIS['openai'], shortcuts=['gpt4o', '4o', 'o']),
    Model(name='open-mixtral-8x7b', api=APIS['mistral'], shortcuts=['mixtral', 'mx']),
    Model(name='mistral-medium-latest', api=APIS['mistral'], shortcuts=['mistral-med', 'md']),
    Model(name='mistral-large-latest', api=APIS['mistral'], shortcuts=['mistral-large', 'ml', 'i']),
    Model(name='llama-3.1-8b-instant', api=APIS['groq'], shortcuts=['llama-small', 'llama-8b', 'ls', 'l8']),
    Model(name='llama-3.1-70b-versatile', api=APIS['groq'], shortcuts=['llama-med', 'llama-70b', 'lm', 'l70']),
    Model(name='llama-3.1-405b-reasoning', api=APIS['groq'], shortcuts=['llama-large', 'llama-405b', 'll', 'l405', 'l']),
    Model(name='claude-3-haiku-20240307', api=APIS['anthropic'], shortcuts=['haiku', 'h']),
    Model(name='claude-3-5-sonnet-20240620', api=APIS['anthropic'], shortcuts=['sonnet', 's']),
    Model(name='claude-3-opus-20240229', api=APIS['anthropic'], shortcuts=['claude', 'opus', 'c']),
]

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}
