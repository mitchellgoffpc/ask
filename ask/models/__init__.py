from dataclasses import dataclass
from ask.models.base import API, Message, Text, Image, ToolRequest, ToolResponse
from ask.models.openai import OpenAIAPI
from ask.models.strawberry import StrawberryAPI
from ask.models.anthropic import AnthropicAPI
from ask.models.deepseek import DeepseekAPI
from ask.models.black_forest_labs import BlackForestLabsAPI

@dataclass
class Model:
    name: str
    api: API
    shortcuts: list[str]
    stream: bool = True


APIS = {
    'openai': OpenAIAPI(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY'),
    'mistral': OpenAIAPI(url='https://api.mistral.ai/v1/chat/completions', key='MISTRAL_API_KEY'),
    'groq': OpenAIAPI(url='https://api.groq.com/openai/v1/chat/completions', key='GROQ_API_KEY'),
    'deepseek': DeepseekAPI(url='https://api.deepseek.com/chat/completions', key='DEEPSEEK_API_KEY'),
    'strawberry': StrawberryAPI(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY'),
    'anthropic': AnthropicAPI(url='https://api.anthropic.com/v1/messages', key='ANTHROPIC_API_KEY'),
    'bfl': BlackForestLabsAPI(url='https://api.bfl.ml/v1/flux-pro-1.1', job_url='https://api.bfl.ml/v1/get_result', key='BFL_API_KEY'),
}

MODELS = [
    Model(name='gpt-3.5-turbo', api=APIS['openai'], shortcuts=['gpt3', '3']),
    Model(name='gpt-4', api=APIS['openai'], shortcuts=['gpt4', '4']),
    Model(name='gpt-4-turbo', api=APIS['openai'], shortcuts=['gpt4t', '4t', 't']),
    Model(name='gpt-4o-mini', api=APIS['openai'], shortcuts=['gpt4o-mini', 'gpt4om', 'gpt4m', '4m']),
    Model(name='gpt-4o', api=APIS['openai'], shortcuts=['gpt4o', '4o']),
    Model(name='o1-mini', api=APIS['strawberry'], shortcuts=['o1m']),
    Model(name='o1-preview', api=APIS['strawberry'], shortcuts=['o1p', 'op']),
    Model(name='o1', api=APIS['strawberry'], shortcuts=['o1', 'o']),
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

__all__ = ['API', 'Message', 'Text', 'Image', 'ToolRequest', 'ToolResponse', 'Model', 'MODELS', 'MODEL_SHORTCUTS']
