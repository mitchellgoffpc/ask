from typing import Any
from ask.models.openai import OpenAIAPI
from ask.models.base import Message, Tool

class StrawberryAPI(OpenAIAPI):
    def render_image(self, mimetype: str, data: bytes) -> dict[str, Any]:
        raise NotImplementedError("O1 API does not currently support image prompts")

    def params(self, model_name: str, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        rendered_msgs = [self.render_message(msg) for msg in messages]
        if system_prompt:  # o1 models don't support a system message
            rendered_msgs = [{"role": "user", "content": system_prompt}, {"role": "assistant", "content": "Understood."}, *rendered_msgs]
        return {"model": model_name, "messages": rendered_msgs, 'stream': self.stream}