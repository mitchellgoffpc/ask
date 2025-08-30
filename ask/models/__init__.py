from ask.models.base import API, Model, Message, Content, Status, Text, TextPrompt, Reasoning, Image, ToolRequest, ToolResponse, ShellCommand
from ask.models.openai import OpenAIAPI
from ask.models.anthropic import AnthropicAPI
from ask.models.google import GoogleAPI
from ask.models.legacy import LegacyOpenAIAPI

APIS = {
    'openai': OpenAIAPI(url='https://api.openai.com/v1/responses', key='OPENAI_API_KEY'),
    'anthropic': AnthropicAPI(url='https://api.anthropic.com/v1/messages', key='_ANTHROPIC_API_KEY'),
    'google': GoogleAPI(url='https://generativelanguage.googleapis.com/v1beta/models', key='GOOGLE_API_KEY'),
    'cerebras': LegacyOpenAIAPI(url='https://api.cerebras.ai/v1/chat/completions', key='CEREBRAS_API_KEY'),
}

MODELS = [
    # OpenAI
    Model(name='gpt-4o', api=APIS['openai'], shortcuts=['gpt4o', '4o']),
    Model(name='gpt-4.1', api=APIS['openai'], shortcuts=['gpt41', '41']),
    Model(name='gpt-5', api=APIS['openai'], shortcuts=['gpt5', '5'], stream=False),
    Model(name='gpt-5-mini', api=APIS['openai'], shortcuts=['gpt5m', '5m'], stream=False),
    Model(name='o1', api=APIS['openai'], shortcuts=['o1']),
    Model(name='o1-pro', api=APIS['openai'], shortcuts=['o1p']),
    Model(name='o3-mini', api=APIS['openai'], shortcuts=['o3m'], supports_images=False),
    Model(name='o3', api=APIS['openai'], shortcuts=['o3']),
    Model(name='o4-mini', api=APIS['openai'], shortcuts=['o4m']),
    # Anthropic
    Model(name='claude-3-5-haiku-latest', api=APIS['anthropic'], shortcuts=['haiku', 'h']),
    Model(name='claude-3-7-sonnet-latest', api=APIS['anthropic'], shortcuts=['sonnet37', 's37']),
    Model(name='claude-sonnet-4-20250514', api=APIS['anthropic'], shortcuts=['sonnet', 's', 'claude', 'c']),
    Model(name='claude-opus-4-1-20250805', api=APIS['anthropic'], shortcuts=['opus', 'o']),
    # Google
    Model(name='gemini-2.0-flash', api=APIS['google'], shortcuts=['gemini2', 'g2'], stream=False),
    Model(name='gemini-2.5-flash', api=APIS['google'], shortcuts=['gemini25', 'g25', 'gemini', 'g']),
    # Cerebras
    Model(name='gpt-oss-120b', api=APIS['cerebras'], shortcuts=['gptoss', 'oss']),
]

MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}

__all__ = [
    'MODELS', 'MODEL_SHORTCUTS',
    'API', 'Model', 'Message', 'Content', 'Status',
    'Text', 'TextPrompt', 'Reasoning', 'Image', 'ToolRequest', 'ToolResponse', 'ShellCommand']
