from ask.tools.base import Tool, Parameter
from ask.tools.bash import BashTool
from ask.tools.grep import GrepTool
from ask.tools.globb import GlobTool
from ask.tools.view import ViewTool
from ask.tools.replace import ReplaceTool
from ask.tools.ls import LSTool

TOOL_LIST = [BashTool(), GlobTool(), GrepTool(), LSTool(), ViewTool(), ReplaceTool()]
TOOLS = {tool.name: tool for tool in TOOL_LIST}

__all__ = ["TOOLS", "Tool", "Parameter"]


if __name__ == "__main__":
    import sys
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Run a specified tool with given arguments.")
    parser.add_argument("tool_name", type=str, choices=TOOLS.keys(), help="The name of the tool to run")
    parser.add_argument("json_args", type=str, help="The JSON string of arguments for the tool")
    args = parser.parse_args()

    try:
        tool = TOOLS[args.tool_name]
        print(tool(json.loads(args.json_args)))
    except json.JSONDecodeError:
        print(f"Error: Arguments must be valid JSON: {args.json_args}")
        sys.exit(1)
