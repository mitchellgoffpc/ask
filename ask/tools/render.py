import re
import json
from ask.tools.base import Tool, Parameter
from ask.models.base import Text, ToolRequest

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
```
""".strip()

def get_tool_schema(params: list[Parameter]) -> str:
    return json.dumps({
        "type": "object",
        "properties": {p.name: {"type": p.type, "description": p.description} for p in params},
        "required": [p.name for p in params if p.required],
        "additionalProperties": False,
        "$schema": "http://json-schema.org/draft-07/schema#",
    }, indent=2)

def render_tools_prompt(tools: list[Tool]) -> str:
    if not tools:
        return ''
    tool_defs = '\n\n'.join(TOOL_DEFINITION.format(name=tool.name, description=tool.description, schema=get_tool_schema(tool.parameters)) for tool in tools)
    return f"{TOOL_PREFIX}\n\n{tool_defs}\n\n{TOOL_USE}"

def parse_tool_block(text: Text) -> list[Text | ToolRequest]:
    result: list[Text | ToolRequest] = []
    content = text.text
    tool_pattern = r"```tool\s+(.*?)\s+```"
    tool_blocks = re.finditer(tool_pattern, content, re.DOTALL)

    # Extract tool blocks and create ToolRequest objects
    for match in tool_blocks:
        try:
            tool_json = json.loads(match.group(1))
            result.append(ToolRequest(tool=tool_json["name"], arguments=tool_json["arguments"]))
        except (json.JSONDecodeError, KeyError):
            continue

    cleaned_text = re.sub(tool_pattern, "", content)
    if cleaned_text.strip():
        result = [Text(text=cleaned_text), *result]
    return result
