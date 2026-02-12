from __future__ import annotations

from ask.tools.base import Tool, ToolError, Parameter
from ask.tools.bash import BashTool
from ask.tools.edit import EditTool
from ask.tools.glob_ import GlobTool
from ask.tools.grep import GrepTool
from ask.tools.list import ListTool
from ask.tools.multi_edit import MultiEditTool
from ask.tools.python import PythonTool
from ask.tools.read import ReadTool
from ask.tools.todo import ToDoTool
from ask.tools.write import WriteTool

TOOL_LIST = [BashTool(), EditTool(), GlobTool(), GrepTool(), ListTool(), MultiEditTool(), PythonTool(), ReadTool(), ToDoTool(), WriteTool()]
TOOLS = {tool.name: tool for tool in TOOL_LIST}

__all__ = [
    "TOOLS", "Tool", "ToolError", "Parameter",
    "BashTool", "EditTool", "GlobTool", "GrepTool", "ListTool", "MultiEditTool", "PythonTool", "ReadTool", "ToDoTool", "WriteTool"]


if __name__ == "__main__":
    import sys
    import json
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run a specified tool with given arguments.")
    parser.add_argument("tool_name", type=str, choices=TOOLS.keys(), help="The name of the tool to run")
    parser.add_argument("json_args", type=str, help="The JSON string of arguments for the tool")
    cli_args = parser.parse_args()

    try:
        tool = TOOLS[cli_args.tool_name]
        args = json.loads(cli_args.json_args)
        tool.check(args)
        artifacts = tool.process(args, tool.artifacts(args))
        print(asyncio.run(tool.run(args, artifacts)))
    except json.JSONDecodeError:
        print(f"Error: Arguments must be valid JSON: {cli_args.json_args}")
        sys.exit(1)
