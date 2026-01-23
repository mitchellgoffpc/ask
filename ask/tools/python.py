from typing import Any

from ask.messages import Blob, Text
from ask.prompts import load_tool_prompt
from ask.shells import PYTHON_SHELL
from ask.tools.base import ToolError, Tool, Parameter, ParameterType


class PythonTool(Tool):
    name = "PythonShell"
    description = load_tool_prompt('python')
    parameters = [
        Parameter("code", "The Python code to execute", ParameterType.String),
        Parameter("timeout", "Optional timeout in milliseconds (max 600000)", ParameterType.Number, required=False),
        Parameter("description", "Clear, concise description of what this code does in 5-10 words", ParameterType.String, required=False)]

    def check(self, args: dict[str, Any]) -> None:
        super().check(args)
        if 'timeout' in args and args['timeout'] > 600000:
            raise ToolError("Timeout cannot exceed 600000ms (10 minutes)")

    async def run(self, args: dict[str, Any], artifacts: dict[str, Any]) -> Blob:
        try:
            nodes = PYTHON_SHELL.parse(args['code'])
        except (SyntaxError, ValueError, OverflowError) as e:
            raise ToolError("Failed to compile code") from e

        timeout_seconds = args.get("timeout", 120000) / 1000.0
        try:
            output, exception = await PYTHON_SHELL.execute(nodes, timeout_seconds)
            if exception:
                raise ToolError(f'Python execution failed\n\n"""\n{exception}\n"""')
            return Text(output)
        except TimeoutError as e:
            raise ToolError(str(e)) from e
