from ask.models.base import API, Model, Message, Text, Image, ToolRequest, ToolResponse
from ask.models.openai import OpenAIAPI, O1API
from ask.models.anthropic import AnthropicAPI
from ask.models.deepseek import DeepseekAPI
from ask.models.black_forest_labs import BlackForestLabsAPI

APIS = {
    'openai': OpenAIAPI(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY'),
    'openai-o1': O1API(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY'),
    'mistral': OpenAIAPI(url='https://api.mistral.ai/v1/chat/completions', key='MISTRAL_API_KEY'),
    'groq': OpenAIAPI(url='https://api.groq.com/openai/v1/chat/completions', key='GROQ_API_KEY'),
    'deepseek': DeepseekAPI(url='https://api.deepseek.com/chat/completions', key='DEEPSEEK_API_KEY'),
    'anthropic': AnthropicAPI(url='https://api.anthropic.com/v1/messages', key='ANTHROPIC_API_KEY'),
    'bfl': BlackForestLabsAPI(url='https://api.bfl.ml/v1/flux-pro-1.1', job_url='https://api.bfl.ml/v1/get_result', key='BFL_API_KEY'),
}

MODELS = [
    Model(name='gpt-3.5-turbo', api=APIS['openai'], shortcuts=['gpt3', '3'], supports_images=False),
    Model(name='gpt-4', api=APIS['openai'], shortcuts=['gpt4', '4'], supports_images=False),
    Model(name='gpt-4-turbo', api=APIS['openai'], shortcuts=['gpt4t', '4t', 't']),
    Model(name='gpt-4o-mini', api=APIS['openai'], shortcuts=['gpt4om', 'gpt4m', '4om', '4m']),
    Model(name='gpt-4o', api=APIS['openai'], shortcuts=['gpt4o', '4o']),
    Model(name='o1-mini', api=APIS['openai-o1'], shortcuts=['o1m'], supports_images=False, supports_tools=False, supports_system_prompt=False),
    Model(name='o1-preview', api=APIS['openai-o1'], shortcuts=['o1p'], supports_images=False, supports_tools=False, supports_system_prompt=False),
    Model(name='o1', api=APIS['openai-o1'], shortcuts=['o1']),
    Model(name='o3-mini', api=APIS['openai-o1'], shortcuts=['o3m'], supports_images=False),
    Model(name='mistral-small-latest', api=APIS['mistral'], shortcuts=['mistral-small', 'ms'], supports_images=False),
    Model(name='mistral-large-latest', api=APIS['mistral'], shortcuts=['mistral-large', 'ml', 'i'], supports_images=False),
    Model(name='pixtral-12b-2409', api=APIS['mistral'], shortcuts=['pixtral-small', 'ps']),
    Model(name='pixtral-large-latest', api=APIS['mistral'], shortcuts=['pixtral-large', 'pl', 'p']),
    Model(name='llama-3.1-8b-instant', api=APIS['groq'], shortcuts=['llama-small', 'llama-8b', 'ls', 'l8'], supports_images=False),
    Model(name='llama-3.3-70b-versatile', api=APIS['groq'], shortcuts=['llama-med', 'llama-70b', 'lm', 'l70'], supports_images=False),
    Model(name='deepseek-chat', api=APIS['deepseek'], shortcuts=['deepseek', 'ds'], supports_images=False),
    Model(name='deepseek-reasoner', api=APIS['deepseek'], shortcuts=['r1'], supports_images=False, supports_tools=False),
    Model(name='claude-3-5-haiku-latest', api=APIS['anthropic'], shortcuts=['haiku', 'h']),
    Model(name='claude-3-7-sonnet-latest', api=APIS['anthropic'], shortcuts=['sonnet', 's', 'claude', 'c']),
    Model(name='flux-pro-1.1', api=APIS['bfl'], shortcuts=['flux', 'f'], stream=False, supports_images=False, supports_tools=False, supports_system_prompt=False),
]

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}

__all__ = ['MODELS', 'MODEL_SHORTCUTS', 'API', 'Model', 'Message', 'Text', 'Image', 'ToolRequest', 'ToolResponse']
