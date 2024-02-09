from typing import List
from dataclasses import dataclass

@dataclass
class API:
  key: str
  url: str

@dataclass
class Model:
  name: str
  api: str
  shortcuts: List[str]

APIS = {
  'openai': API(url='https://api.openai.com/v1/chat/completions', key='OPENAI_API_KEY'),
  'mistral': API(url='https://api.mistral.ai/v1/chat/completions', key='MISTRAL_API_KEY'),
}
MODELS = [
  Model(name='gpt-3.5-turbo', api='openai', shortcuts=['gpt3', '3']),
  Model(name='gpt-4', api='openai', shortcuts=['gpt4', '4']),
  Model(name='gpt-4-turbo-preview', api='openai', shortcuts=['gpt4t', '4t', 't']),
  Model(name='mistral-medium', api='mistral', shortcuts=['mistral', 'i']),
]
