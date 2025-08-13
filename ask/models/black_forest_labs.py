import os
import requests
import time
from dataclasses import dataclass
from typing import Any, Tuple

from ask.models.base import API, Model, Tool, Message, Content, Text, Image, ToolRequest, ToolResponse, get_message_groups

@dataclass
class BlackForestLabsAPI(API):
    job_url: str

    def render_image(self, image: Image) -> dict[str, Any]:
        raise NotImplementedError("Black Forest Labs API does not currently support image prompts")

    def render_tool_request(self, tool_request: ToolRequest) -> dict[str, Any]:
        raise NotImplementedError("Black Forest Labs API does not currently support tools")

    def render_tool_response(self, tool_response: ToolResponse) -> dict[str, Any]:
        raise NotImplementedError("Black Forest Labs API does not currently support tools")

    def render_tool(self, tool: Tool) -> dict[str, Any]:
        raise NotImplementedError("Black Forest Labs API does not currently support tools")

    def decode_chunk(self, chunk: str) -> Tuple[str, str, str]:
        raise NotImplementedError("Black Forest Labs API does not currently support streaming")

    def headers(self, api_key: str) -> dict[str, str]:
        return {"x-key": api_key, "accept": "application/json", "Content-Type": "application/json"}

    def params(self, model: Model, messages: list[Message], tools: list[Tool], system_prompt: str = '', temperature: float = 0.7) -> dict[str, Any]:
        groups = get_message_groups(messages)
        assert len(groups) > 0, "You must specify a prompt for image generation"
        _, prompt = groups[-1]
        text_prompt = [msg for msg in prompt if isinstance(msg, Text)]
        assert len(text_prompt) > 0, "You must specify a prompt for image generation"
        return {"prompt": text_prompt[-1].text, "width": 1024, "height": 1024}

    def result(self, response: dict[str, Any]) -> list[Content]:
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
                sample: str = result['result']['sample']
                return sample
            elif result["status"] == "Failed":
                raise RuntimeError(f"Image generation failed: {result.get('error', 'Unknown error')}")
            else:
                raise RuntimeError(f"Image generation returned unknown status: {result['status']}")

    def query_result(self, url: str) -> bytes:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        return b''.join(r)
