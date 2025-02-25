import os
import json
import time
import base64
import requests
from typing import Any, Iterator
from dataclasses import dataclass

@dataclass
class Text:
    text: str

@dataclass
class Image:
    mimetype: str
    data: bytes

@dataclass
class Message:
    role: str
    content: list[Text | Image]


@dataclass
class API:
    key: str
    url: str
    stream: bool

    def render_text(self, text: str) -> dict[str, Any]:
        return {'type': 'text', 'text': text}

    def render_image(self, mimetype: str, data: bytes) -> dict[str, Any]:
        return {'type': 'image_url', 'image_url': {'url': f'data:{mimetype};base64,{base64.b64encode(data).decode()}'}}

    def render_item(self, item: Text | Image) -> dict[str, Any]:
        if isinstance(item, Text):
            return self.render_text(item.text)
        else:
            return self.render_image(item.mimetype, item.data)

    def render_message(self, message: Message) -> dict[str, Any]:
        return {'role': message.role, 'content': [self.render_item(item) for item in message.content]}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def params(self, model_name: str, prompt: list[Message], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        messages = [self.render_message(msg) for msg in prompt]
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}, *messages]
        return {"model": model_name, "messages": messages, "temperature": temperature, 'max_tokens': 4096, 'stream': self.stream}

    def result(self, response: dict[str, Any]) -> bytes:
        assert len(response['choices']) == 1, f"Expected exactly one choice, but got {len(response['choices'])}!"
        return response['choices'][0]['message']['content'].encode()

    def decode(self, chunks: Iterator[str]) -> Iterator[bytes]:
        for chunk in chunks:
            yield self.decode_chunk(chunk)

    def decode_chunk(self, chunk: str) -> bytes:
        if chunk.startswith("data: ") and chunk != 'data: [DONE]':
            line = json.loads(chunk[6:])
            return line['choices'][0]['delta'].get('content', '').encode()
        else:
            return b''

class StrawberryAPI(API):
    def render_image(self, mimetype: str, data: bytes) -> dict[str, str | dict[str, str]]:
        raise NotImplementedError("O1 API does not currently support image prompts")

    def params(self, model_name: str, prompt: list[Message], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        messages = [self.render_message(msg) for msg in prompt]
        if system_prompt:  # o1 models don't support a system message
            messages = [{"role": "user", "content": system_prompt}, {"role": "assistant", "content": "Understood."}, *messages]
        return {"model": model_name, "messages": messages, 'stream': self.stream}

class AnthropicAPI(API):
    def render_image(self, mimetype: str, data: bytes) -> dict[str, str | dict[str, str]]:
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': mimetype, 'data': base64.b64encode(data).decode()}}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-api-key": api_key, 'anthropic-version': '2023-06-01'}

    def params(self, model_name: str, prompt: list[Message], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        messages = [self.render_message(msg) for msg in prompt]
        system = {'system': system_prompt} if system_prompt else {}
        return {"model": model_name, "messages": messages, "temperature": temperature, 'max_tokens': 4096, 'stream': self.stream} | system

    def result(self, response: dict[str, Any]) -> bytes:
        assert len(response['content']) == 1, f"Expected exactly one choice, but got {len(response['content'])}!"
        return response['content'][0]['text'].encode()

    def decode_chunk(self, chunk: str) -> bytes:
        if chunk.startswith("data: ") and chunk != 'data: [DONE]':
            line = json.loads(chunk[6:])
            if line['type'] == 'content_block_delta':
                return line['delta']['text'].encode()
        return b''

class DeepseekAPI(API):
    def result(self, response: dict[str, Any]) -> bytes:
        assert len(response['choices']) == 1, f"Expected exactly one choice, but got {len(response['choices'])}!"
        message = response['choices'][0]['message']
        content = message['content']
        if message.get('reasoning_content'):
            content = f"<think>\n{message['reasoning_content']}\n</think>\n\n{content}"
        return content.encode()

    def decode(self, chunks: Iterator[str]) -> Iterator[bytes]:
        reasoning = False
        for chunk in chunks:
            if chunk.startswith("data: ") and chunk != 'data: [DONE]':
                line = json.loads(chunk[6:])
                delta = line['choices'][0]['delta']
                next_reasoning = bool(delta.get('reasoning_content'))
                if not reasoning and next_reasoning:
                    yield b'<think>\n'
                if reasoning and not next_reasoning:
                    yield b'\n</think>\n\n'
                reasoning = next_reasoning
                content = delta.get('content') or delta.get('reasoning_content') or ''
                yield content.encode()

@dataclass
class BlackForestLabsAPI(API):
    job_url: str

    def render_image(self, mimetype: str, data: bytes) -> dict[str, str | dict[str, str]]:
        raise NotImplementedError("Black Forest Labs API does not currently support image prompts")

    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-key": api_key, "accept": "application/json", "Content-Type": "application/json"}

    def params(self, model_name: str, prompt: list[Message], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        assert len(prompt) > 0, 'You must specify a prompt for image generation'
        text_prompt = [msg for msg in prompt[-1].content if isinstance(msg, Text)]
        assert len(text_prompt) > 0, 'You must specify a prompt for image generation'
        return {"prompt": text_prompt[-1].text, "width": 1024, "height": 1024}

    def result(self, response: dict[str, Any]) -> bytes:
        # Black Forest Labs API is a bit different, the initial request returns a job ID and you poll that job to get the final result url
        result_url = self.query_job_status(response['id'])
        result = self.query_result(result_url)
        return result

    def query_job_status(self, job_id: str) -> str:
        api_key = os.getenv(self.key, '')
        headers = self.headers(api_key)
        while True:  # Poll for the result
            time.sleep(0.5)
            r = requests.get(self.job_url, headers=headers, params={'id': job_id})
            r.raise_for_status()

            result = r.json()
            if result["status"] == "Pending":
                pass
            elif result["status"] == "Ready":
                return result['result']['sample']
            elif result["status"] == "Failed":
                raise RuntimeError(f"Image generation failed: {result.get('error', 'Unknown error')}")
            else:
                raise RuntimeError(f"Image generation returned unknown status: {result['status']}")

    def query_result(self, url: str) -> bytes:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        return b''.join(r)


@dataclass
class Model:
    name: str
    api: API
    shortcuts: list[str]

class TextModel(Model): pass
class ImageModel(Model): pass


APIS = {
    'openai': API(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY', stream=True),
    'mistral': API(url='https://api.mistral.ai/v1/chat/completions', key='MISTRAL_API_KEY', stream=True),
    'groq': API(url='https://api.groq.com/openai/v1/chat/completions', key='GROQ_API_KEY', stream=True),
    'deepseek': DeepseekAPI(url='https://api.deepseek.com/chat/completions', key='DEEPSEEK_API_KEY', stream=True),
    'strawberry': StrawberryAPI(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY', stream=True),
    'strawberry-ns': StrawberryAPI(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY', stream=False),
    'anthropic': AnthropicAPI(url='https://api.anthropic.com/v1/messages', key='ANTHROPIC_API_KEY', stream=True),
    'bfl': BlackForestLabsAPI(url='https://api.bfl.ml/v1/flux-pro-1.1', job_url='https://api.bfl.ml/v1/get_result', key='BFL_API_KEY', stream=False),
}

MODELS = [
    TextModel(name='gpt-3.5-turbo', api=APIS['openai'], shortcuts=['gpt3', '3']),
    TextModel(name='gpt-4', api=APIS['openai'], shortcuts=['gpt4', '4']),
    TextModel(name='gpt-4-turbo', api=APIS['openai'], shortcuts=['gpt4t', '4t', 't']),
    TextModel(name='gpt-4o-mini', api=APIS['openai'], shortcuts=['gpt4o-mini', 'gpt4om', 'gpt4m', '4m']),
    TextModel(name='gpt-4o', api=APIS['openai'], shortcuts=['gpt4o', '4o']),
    TextModel(name='o1-mini', api=APIS['strawberry'], shortcuts=['o1m']),
    TextModel(name='o1-preview', api=APIS['strawberry'], shortcuts=['o1p', 'op']),
    TextModel(name='o1', api=APIS['strawberry-ns'], shortcuts=['o1', 'o']),
    TextModel(name='o3-mini', api=APIS['strawberry'], shortcuts=['o3m', 'om']),
    TextModel(name='open-mixtral-8x7b', api=APIS['mistral'], shortcuts=['mixtral', 'mx']),
    TextModel(name='mistral-medium-latest', api=APIS['mistral'], shortcuts=['mistral-med', 'md']),
    TextModel(name='mistral-large-latest', api=APIS['mistral'], shortcuts=['mistral-large', 'ml', 'i']),
    TextModel(name='llama-3.1-8b-instant', api=APIS['groq'], shortcuts=['llama-small', 'llama-8b', 'ls', 'l8']),
    TextModel(name='llama-3.3-70b-versatile', api=APIS['groq'], shortcuts=['llama-med', 'llama-70b', 'lm', 'l70']),
    TextModel(name='deepseek-reasoner', api=APIS['deepseek'], shortcuts=['r1']),
    TextModel(name='claude-3-5-haiku-latest', api=APIS['anthropic'], shortcuts=['haiku', 'h']),
    TextModel(name='claude-3-7-sonnet-latest', api=APIS['anthropic'], shortcuts=['sonnet', 's']),
    ImageModel(name='flux-pro-1.1', api=APIS['bfl'], shortcuts=['flux', 'f']),
]

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}
