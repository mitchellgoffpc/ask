from ask.models.anthropic import AnthropicAPI
from ask.models.base import API, Capabilities, Context, Model, Pricing
from ask.models.google import GoogleAPI
from ask.models.legacy import LegacyOpenAIAPI
from ask.models.openai import OpenAIAPI

APIS = {
    'openai': OpenAIAPI(url='https://api.openai.com/v1/responses', key='OPENAI_API_KEY', display_name='OpenAI'),
    'anthropic': AnthropicAPI(url='https://api.anthropic.com/v1/messages', key='ANTHROPIC_API_KEY', display_name='Anthropic'),
    'google': GoogleAPI(url='https://generativelanguage.googleapis.com/v1beta/models', key='GOOGLE_API_KEY', display_name='Google'),
    'openrouter': LegacyOpenAIAPI(url='https://openrouter.ai/api/v1/chat/completions', key='OPENROUTER_API_KEY', display_name='OpenRouter'),
}

MODELS = [
    # OpenAI
    Model(APIS['openai'], 'gpt-4o', ['gpt4o', '4o'], Context(128_000, 16_000), Pricing(2.50, 2.50, 1.25, 10.00), Capabilities(reasoning=False)),
    Model(APIS['openai'], 'gpt-4.1', ['gpt41', '41'], Context(1_000_000, 32_000), Pricing(2.00, 2.00, 0.50, 8.00), Capabilities(reasoning=False)),
    Model(APIS['openai'], 'gpt-5', ['gpt5', '5'], Context(400_000, 128_000), Pricing(1.25, 1.25, 0.125, 10.00), Capabilities(stream=False)),
    Model(APIS['openai'], 'gpt-5-mini', ['gpt5m', '5m'], Context(400_000, 128_000), Pricing(0.25, 0.25, 0.025, 2.00), Capabilities(stream=False)),
    Model(APIS['openai'], 'gpt-5-nano', ['gpt5n', '5n'], Context(400_000, 128_000), Pricing(0.05, 0.05, 0.005, 0.4), Capabilities(stream=False)),
    Model(APIS['openai'], 'gpt-5-codex', ['gpt5c', '5c'], Context(400_000, 128_000), Pricing(1.00, 1.00, 0.10, 4.00), Capabilities(stream=False)),
    Model(APIS['openai'], 'o3-mini', ['o3m'], Context(200_000, 100_000), Pricing(0.60, 0.75, 0.06, 3.00), Capabilities(images=False)),
    Model(APIS['openai'], 'o3', ['o3'], Context(200_000, 100_000), Pricing(2.00, 2.00, 0.50, 8.00), Capabilities()),
    Model(APIS['openai'], 'o3-pro', ['o3p'], Context(200_000, 100_000), Pricing(20.00, 20.00, 20.00, 80.00), Capabilities()),
    Model(APIS['openai'], 'o4-mini', ['o4m'], Context(200_000, 100_000), Pricing(1.10, 1.10, 0.275, 4.40), Capabilities()),
    # Anthropic
    Model(APIS['anthropic'], 'claude-haiku-4-5', ['haiku', 'h'], Context(200_000, 64_000), Pricing(1.0, 1.25, 0.10, 5.0), Capabilities(reasoning=False)),
    Model(APIS['anthropic'], 'claude-sonnet-4-5', ['sonnet', 's'], Context(200_000, 64_000), Pricing(3.00, 3.75, 0.30, 15.00), Capabilities()),
    Model(APIS['anthropic'], 'claude-opus-4-5', ['opus', 'o'], Context(200_000, 64_000), Pricing(5.00, 6.25, 0.50, 25.00), Capabilities()),
    # Google
    Model(APIS['google'], 'gemini-2.0-flash', ['gemini2', 'g2'], Context(1_000_000, 64_000), None, Capabilities(stream=False, reasoning=False)),
    Model(APIS['google'], 'gemini-2.5-flash', ['gemini25', 'g25', 'gemini', 'g'], Context(1_000_000, 64_000), None, Capabilities(reasoning=False)),
    # OpenRouter
    Model(APIS['openrouter'], 'gpt-oss-120b', ['gptoss', 'oss'], Context(128_000, 128_000), None, Capabilities(stream=False)),
]

MODELS_BY_NAME = {model.name: model for model in MODELS}
MODEL_SHORTCUTS = {s: model for model in MODELS for s in [model.name, *model.shortcuts]}

__all__ = ['MODELS', 'MODEL_SHORTCUTS', 'API', 'Model', 'Pricing', 'Context', 'Capabilities']
