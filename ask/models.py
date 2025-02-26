import os
import json
import time
import base64
import requests
from typing import Any, Iterator
from dataclasses import dataclass
from ask.tools import Tool, Parameter

@dataclass
class Text:
    text: str

@dataclass
class Image:
    mimetype: str
    data: bytes

@dataclass
class ToolRequest:
    tool: str
    arguments: dict[str, str]

@dataclass
class ToolResponse:
    tool: str
    response: str

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

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        params = {p.name: self.render_tool_param(p) for p in tool.parameters}
        required = [p.name for p in tool.parameters if p.required]
        return {
            'type': 'function',
            'function': {
                'name': tool.name,
                'description': tool.description,
                'parameters': {'type': 'object', 'properties': params, 'required': required}}}

    def render_tool_param(self, param: Parameter) -> dict[str, Any]:
        rendered: dict[str, Any] = {'type': param.type}
        if param.description:
            rendered['description'] = param.description
        if param.enum:
            rendered['enum'] = param.enum
        return rendered

    def headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def params(self, model_name: str, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        rendered_msgs = [self.render_message(msg) for msg in messages]
        rendered_tools = [self.render_tool(tool) for tool in tools]
        if system_prompt:
            rendered_msgs = [{"role": "system", "content": system_prompt}, *rendered_msgs]
        return {"model": model_name, "messages": rendered_msgs, "tools": rendered_tools, "temperature": temperature, 'max_tokens': 4096, 'stream': self.stream}

    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]:
        result: list[Text | Image | ToolRequest] = []
        for item in response['choices']:
            if item['message'].get('content'):
                result.append(Text(text=item['message']['content']))
            for call in item['message'].get('tool_calls') or []:
                result.append(ToolRequest(tool=call['function']['name'], arguments=json.loads(call['function']['arguments'])))
        return result

    def decode(self, chunks: Iterator[str]) -> Iterator[tuple[str, Text | Image | ToolRequest | None]]:
        current_idx, current_tool = -1, ''
        current_data: list[str] = []
        for chunk in chunks:
            idx, tool, data = self.decode_chunk(chunk)
            if idx is not None and idx != current_idx:
                yield '', self.flush_chunk(current_tool, ''.join(current_data))
                current_idx, current_tool, current_data = idx, '', []
            current_tool = current_tool or tool
            current_data.append(data)
            if not current_tool:
                yield data, None
        yield '', self.flush_chunk(current_tool, ''.join(current_data))

    def decode_chunk(self, chunk: str) -> tuple[int | None, str, str]:
        if not chunk.startswith("data: ") or chunk == 'data: [DONE]':
            return None, '', ''
        line = json.loads(chunk[6:])
        assert len(line['choices']) <= 1, f"Expected exactly one choice, but got {len(line['choices'])}!"
        if not line['choices'] or 'delta' not in line['choices'][0]:
            return None, '', ''
        delta = line['choices'][0]['delta']
        if 'tool_calls' in delta:
            assert len(delta['tool_calls']) == 1, f"Expected exactly one tool call, but got {len(delta['tool_calls'])}!"
            tool = delta['tool_calls'][0]['function']
            return line['choices'][0]['index'], tool.get('name', ''), tool['arguments']
        elif delta.get('content'):
            return line['choices'][0]['index'], '', delta['content']
        else:
            return None, '', ''

    def flush_chunk(self, tool: str, data: str) -> Text | Image | ToolRequest | None:
        if tool:
            return ToolRequest(tool=tool, arguments=json.loads(data))
        elif data:
            return Text(text=data)
        else:
            return None

class StrawberryAPI(API):
    def render_image(self, mimetype: str, data: bytes) -> dict[str, str | dict[str, str]]:
        raise NotImplementedError("O1 API does not currently support image prompts")

    def params(self, model_name: str, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        rendered_msgs = [self.render_message(msg) for msg in messages]
        if system_prompt:  # o1 models don't support a system message
            rendered_msgs = [{"role": "user", "content": system_prompt}, {"role": "assistant", "content": "Understood."}, *rendered_msgs]
        return {"model": model_name, "messages": rendered_msgs, 'stream': self.stream}

class AnthropicAPI(API):
    def render_image(self, mimetype: str, data: bytes) -> dict[str, str | dict[str, str]]:
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': mimetype, 'data': base64.b64encode(data).decode()}}

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        params = {p.name: self.render_tool_param(p) for p in tool.parameters}
        required = [p.name for p in tool.parameters if p.required]
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {'type': 'object', 'properties': params, 'required': required}}

    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-api-key": api_key, 'anthropic-version': '2023-06-01'}

    def params(self, model_name: str, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        rendered_msgs = [self.render_message(msg) for msg in messages]
        rendered_tools = [self.render_tool(tool) for tool in tools]
        system = {'system': system_prompt} if system_prompt else {}
        return {"model": model_name, "messages": rendered_msgs, "tools": rendered_tools, "temperature": temperature, 'max_tokens': 4096, 'stream': self.stream} | system

    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]:
        result: list[Text | Image | ToolRequest] = []
        for item in response['content']:
            if item['type'] == 'text':
                result.append(Text(text=item['text']))
            elif item['type'] == 'tool_use':
                result.append(ToolRequest(tool=item['name'], arguments=item['input']))
        return result

    def decode_chunk(self, chunk: str) -> tuple[int | None, str, str]:
        if not chunk.startswith("data: ") or chunk == 'data: [DONE]':
            return None, '', ''
        line = json.loads(chunk[6:])
        if line['type'] == 'content_block_start' and line['content_block']['type'] == 'tool_use':
            assert not line['content_block']['input'], "Expected no input for content_block_start"
            return line['index'], line['content_block']['name'], ''
        elif line['type'] == 'content_block_delta':
            if line['delta']['type'] == 'input_json_delta':
                return line['index'], '', line['delta']['partial_json']
            elif line['delta']['type'] == 'text_delta':
                return line['index'], '', line['delta']['text']
        return None, '', ''

class DeepseekAPI(API):
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

@dataclass
class BlackForestLabsAPI(API):
    job_url: str

    def render_image(self, mimetype: str, data: bytes) -> dict[str, str | dict[str, str]]:
        raise NotImplementedError("Black Forest Labs API does not currently support image prompts")

    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-key": api_key, "accept": "application/json", "Content-Type": "application/json"}

    def params(self, model_name: str, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        assert len(messages) > 0, 'You must specify a prompt for image generation'
        text_prompt = [msg for msg in messages[-1].content if isinstance(msg, Text)]
        assert len(text_prompt) > 0, 'You must specify a prompt for image generation'
        return {"prompt": text_prompt[-1].text, "width": 1024, "height": 1024}

    def result(self, response: dict[str, Any]) -> list[Text | Image | ToolRequest]:
        # Black Forest Labs API is a bit different, the initial request returns a job ID and you poll that job to get the final result url
        result_url = self.query_job_status(response['id'])
        result = self.query_result(result_url)
        return [Image(mimetype='image/jpeg', data=result)]

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
    Model(name='gpt-3.5-turbo', api=APIS['openai'], shortcuts=['gpt3', '3']),
    Model(name='gpt-4', api=APIS['openai'], shortcuts=['gpt4', '4']),
    Model(name='gpt-4-turbo', api=APIS['openai'], shortcuts=['gpt4t', '4t', 't']),
    Model(name='gpt-4o-mini', api=APIS['openai'], shortcuts=['gpt4o-mini', 'gpt4om', 'gpt4m', '4m']),
    Model(name='gpt-4o', api=APIS['openai'], shortcuts=['gpt4o', '4o']),
    Model(name='o1-mini', api=APIS['strawberry'], shortcuts=['o1m']),
    Model(name='o1-preview', api=APIS['strawberry'], shortcuts=['o1p', 'op']),
    Model(name='o1', api=APIS['strawberry-ns'], shortcuts=['o1', 'o']),
    Model(name='o3-mini', api=APIS['strawberry'], shortcuts=['o3m', 'om']),
    Model(name='open-mixtral-8x7b', api=APIS['mistral'], shortcuts=['mixtral', 'mx']),
    Model(name='mistral-small-latest', api=APIS['mistral'], shortcuts=['mistral-small', 'ms']),
    Model(name='mistral-medium-latest', api=APIS['mistral'], shortcuts=['mistral-med', 'md']),
    Model(name='mistral-large-latest', api=APIS['mistral'], shortcuts=['mistral-large', 'ml', 'i']),
    Model(name='llama-3.1-8b-instant', api=APIS['groq'], shortcuts=['llama-small', 'llama-8b', 'ls', 'l8']),
    Model(name='llama-3.3-70b-versatile', api=APIS['groq'], shortcuts=['llama-med', 'llama-70b', 'lm', 'l70']),
    Model(name='deepseek-reasoner', api=APIS['deepseek'], shortcuts=['r1']),
    Model(name='claude-3-5-haiku-latest', api=APIS['anthropic'], shortcuts=['haiku', 'h']),
    Model(name='claude-3-7-sonnet-latest', api=APIS['anthropic'], shortcuts=['sonnet', 's']),
    Model(name='flux-pro-1.1', api=APIS['bfl'], shortcuts=['flux', 'f']),
]

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}
