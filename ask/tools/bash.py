import asyncio
from typing import Any

from ask.models.base import Blob, Text
from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter, ParameterType

class BashTool(Tool):
    name = "BashShell"
    description = load_tool_prompt('bash')
    parameters = [
        Parameter("command", "The command to execute", ParameterType.String),
        Parameter("timeout", "Optional timeout in milliseconds (max 600000)", ParameterType.Number, required=False),
        Parameter("description",
            "Clear, concise description of what this command does in 5-10 words. Examples:\n"
            "Input: ls\nOutput: Lists files in current directory\n\n"
            "Input: git status\nOutput: Shows working tree status\n\n"
            "Input: npm install\nOutput: Installs package dependencies\n\n"
            "Input: mkdir foo\nOutput: Creates directory 'foo'", ParameterType.String, required=False)]



    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        timeout_seconds = args.get("timeout", 120000) / 1000.0  # Default 2 minutes
        if timeout_seconds > 600:
            raise ToolError("Timeout cannot exceed 600000ms (10 minutes)")
        return {'command': args["command"], 'timeout_seconds': timeout_seconds}

    async def run(self, command: str, timeout_seconds: float) -> Blob:
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
            output = stdout.decode('utf-8').rstrip('\n')
            if process.returncode != 0:
                raise ToolError(output)
            return Text(output)
        except asyncio.TimeoutError:
            raise ToolError(f"Command timed out after {timeout_seconds} seconds") from None
