from ask.models.base import API, Model, Pricing, Message, Content, Text, Reasoning, Image, ToolRequest, ToolResponse, Command, Usage, Error
from ask.models.openai import OpenAIAPI
from ask.models.anthropic import AnthropicAPI
from ask.models.google import GoogleAPI
from ask.models.legacy import LegacyOpenAIAPI

APIS = {
    'openai': OpenAIAPI(url='https://api.openai.com/v1/responses', key='OPENAI_API_KEY', display_name='OpenAI'),
    'anthropic': AnthropicAPI(url='https://api.anthropic.com/v1/messages', key='_ANTHROPIC_API_KEY', display_name='Anthropic'),
    'google': GoogleAPI(url='https://generativelanguage.googleapis.com/v1beta/models', key='GOOGLE_API_KEY', display_name='Google'),
    'openrouter': LegacyOpenAIAPI(url='https://openrouter.ai/api/v1/chat/completions', key='OPENROUTER_API_KEY', display_name='OpenRouter'),
}

MODELS = [
    # OpenAI
    Model(name='gpt-4o', api=APIS['openai'], pricing=Pricing(2.50, 2.50, 1.25, 10.00), shortcuts=['gpt4o', '4o'], supports_reasoning=False),
    Model(name='gpt-4.1', api=APIS['openai'], pricing=Pricing(2.00, 2.00, 0.50, 8.00), shortcuts=['gpt41', '41'], supports_reasoning=False),
    Model(name='gpt-5', api=APIS['openai'], pricing=Pricing(1.25, 1.25, 0.125, 10.00), shortcuts=['gpt5', '5'], stream=False),
    Model(name='gpt-5-mini', api=APIS['openai'], pricing=Pricing(0.25, 0.25, 0.025, 2.00), shortcuts=['gpt5m', '5m'], stream=False),
    Model(name='gpt-5-nano', api=APIS['openai'], pricing=Pricing(0.05, 0.05, 0.005, 0.4), shortcuts=['gpt5n', '5n'], stream=False),
    Model(name='gpt-5-codex', api=APIS['openai'], pricing=Pricing(1.00, 1.00, 0.10, 4.00), shortcuts=['gpt5c', '5c'], stream=False),
    Model(name='o1', api=APIS['openai'], pricing=Pricing(15.00, 15.00, 7.50, 60.00), shortcuts=['o1']),
    Model(name='o1-pro', api=APIS['openai'], pricing=Pricing(150.00, 150.00, 150.00, 600.00), shortcuts=['o1p']),
    Model(name='o3-mini', api=APIS['openai'], pricing=Pricing(0.60, 0.75, 0.06, 3.00), shortcuts=['o3m'], supports_images=False),
    Model(name='o3', api=APIS['openai'], pricing=Pricing(2.00, 2.00, 0.50, 8.00), shortcuts=['o3']),
    Model(name='o3-pro', api=APIS['openai'], pricing=Pricing(20.00, 20.00, 20.00, 80.00), shortcuts=['o3p']),
    Model(name='o4-mini', api=APIS['openai'], pricing=Pricing(1.10, 1.10, 0.275, 4.40), shortcuts=['o4m']),
    # Anthropic
    Model(name='claude-3-5-haiku-latest',  api=APIS['anthropic'], pricing=Pricing(0.80, 1.00, 0.08, 4.00), shortcuts=['haiku', 'h'], supports_reasoning=False),
    Model(name='claude-3-7-sonnet-latest', api=APIS['anthropic'], pricing=Pricing(3.00, 3.75, 0.30, 15.00), shortcuts=['sonnet37', 's37']),
    Model(name='claude-sonnet-4-20250514', api=APIS['anthropic'], pricing=Pricing(3.00, 3.75, 0.30, 15.00), shortcuts=['sonnet', 's', 'claude', 'c']),
    Model(name='claude-opus-4-1-20250805', api=APIS['anthropic'], pricing=Pricing(15.00, 18.75, 1.50, 75.00), shortcuts=['opus', 'o']),
    # Google
    Model(name='gemini-2.0-flash', api=APIS['google'], shortcuts=['gemini2', 'g2'], stream=False, supports_reasoning=False),
    Model(name='gemini-2.5-flash', api=APIS['google'], shortcuts=['gemini25', 'g25', 'gemini', 'g'], supports_reasoning=False),
    # OpenRouter
    Model(name='gpt-oss-120b', api=APIS['openrouter'], shortcuts=['gptoss', 'oss'], stream=False),
]

MODELS_BY_NAME = {model.name: model for model in MODELS}
MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}

__all__ = [
    'MODELS', 'MODEL_SHORTCUTS',
    'API', 'Model', 'Pricing', 'Message', 'Content',
    'Text', 'Reasoning', 'Image', 'ToolRequest', 'ToolResponse', 'Command', 'Usage', 'Error']
