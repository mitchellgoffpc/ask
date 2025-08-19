from ask.tools.base import Tool, Parameter
# from ask.tools.bash import BashTool
from ask.tools.glob_ import GlobTool
from ask.tools.grep import GrepTool
from ask.tools.edit import EditTool
from ask.tools.list import ListTool
from ask.tools.python import PythonTool
from ask.tools.read import ReadTool
from ask.tools.write import WriteTool

TOOL_LIST = [GlobTool(), GrepTool(), EditTool(), ListTool(), PythonTool(), ReadTool(), WriteTool()]
TOOLS = {tool.name: tool for tool in TOOL_LIST}

__all__ = ["TOOLS", "Tool", "Parameter"]


if __name__ == "__main__":
    import sys
    import json
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run a specified tool with given arguments.")
    parser.add_argument("tool_name", type=str, choices=TOOLS.keys(), help="The name of the tool to run")
    parser.add_argument("json_args", type=str, help="The JSON string of arguments for the tool")
    args = parser.parse_args()

    try:
        tool = TOOLS[args.tool_name]
        print(asyncio.run(tool(json.loads(args.json_args))))
    except json.JSONDecodeError:
        print(f"Error: Arguments must be valid JSON: {args.json_args}")
        sys.exit(1)
