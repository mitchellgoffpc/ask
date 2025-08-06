import re
import json
import uuid

from ask.tools import Tool
from ask.models.base import Text, ToolRequest, ToolResponse

# Since not all models support tool use directly, we also need to be able render the tools as a normal user message.
TOOL_PREFIX = "You have access to the following tools, which you can use if they seem helpful for accomplishing the user's request:"
TOOL_DEFINITION = """
```tool
name: {name}
description: {description}
argument-schema:
{schema}
```
""".strip()

TOOL_USE = """
To use a tool, respond with a tool block in the following format. Your response can contain multiple tool blocks if you want to use multiple tools at once.

```tool
{
  "name": <tool-name>,
  "arguments": {
    <argument-name>: <argument-value>,
    ...
  }
}

The tool output will be displayed in a separate tool block, like this:

```tool
tool: <tool-name>
response: <response>
```
""".strip()

TOOL_REQUEST = """
```tool
{{
  "call_id": {call_id}
  "name": {name}
  "arguments": {arguments}
}}
```
""".strip()

TOOL_RESPONSE = """
```tool
call_id: {call_id}
tool: {name}
response:
{response}
```
""".strip()

def render_tool_definition(tool: Tool) -> str:
    schema = json.dumps(tool.get_input_schema(), indent=2)
    return TOOL_DEFINITION.format(name=tool.name, description=tool.description, schema=schema)

def render_tools_prompt(tools: list[Tool]) -> str:
    if not tools:
        return ''
    tool_definitions = '\n\n'.join(render_tool_definition(tool) for tool in tools)
    return f"{TOOL_PREFIX}\n\n{tool_definitions}\n\n{TOOL_USE}"

def render_tool_request(request: ToolRequest) -> str:
    return TOOL_REQUEST.format(call_id=request.call_id, name=request.tool, arguments=json.dumps(request.arguments))

def render_tool_response(response: ToolResponse) -> str:
    return TOOL_RESPONSE.format(call_id=response.call_id, name=response.tool, response=response.response)

def parse_tool_block(text: Text) -> list[Text | ToolRequest]:
    result: list[Text | ToolRequest] = []
    content = text.text
    tool_pattern = r"```tool\s+(.*?)\s+```"
    tool_blocks = re.finditer(tool_pattern, content, re.DOTALL)

    # Extract tool blocks and create ToolRequest objects
    for match in tool_blocks:
        try:
            tool_json = json.loads(match.group(1))
            result.append(ToolRequest(call_id=f'tooluse-{uuid.uuid4()}', tool=tool_json["name"], arguments=tool_json["arguments"]))
        except (json.JSONDecodeError, KeyError):
            continue

    cleaned_text = re.sub(tool_pattern, "", content, flags=re.DOTALL).strip()
    if cleaned_text:
        result = [Text(text=cleaned_text), *result]
    return result
