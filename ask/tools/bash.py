import asyncio
from typing import Any

from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter
from ask.ui.styles import Colors, Theme

class BashTool(Tool):
    name = "Bash"
    description = load_tool_prompt('bash')
    parameters = [
        Parameter("command", "string", "The command to execute"),
        Parameter("timeout", "number", "Optional timeout in milliseconds (max 600000)", required=False),
        Parameter("description", "string",
            "Clear, concise description of what this command does in 5-10 words. Examples:\n"
            "Input: ls\nOutput: Lists files in current directory\n\n"
            "Input: git status\nOutput: Shows working tree status\n\n"
            "Input: npm install\nOutput: Installs package dependencies\n\n"
            "Input: mkdir foo\nOutput: Creates directory 'foo'", required=False)]

    def render_args(self, args: dict[str, str]) -> str:
        return args['command']

    def render_short_response(self, response: str) -> str:
        lines = response.strip().split('\n')
        if len(lines) <= 3:
            return response.strip()
        abbreviated = '\n'.join(lines[:3])
        elipsis = Colors.hex(f"… +{len(lines) - 3} lines (ctrl+r to expand)", Theme.GRAY)
        return f"{abbreviated}\n{elipsis}"

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        timeout_seconds = args.get("timeout", 120000) / 1000.0  # Default 2 minutes
        if timeout_seconds > 600:
            raise ToolError("Timeout cannot exceed 600000ms (10 minutes)")
        return {'command': args["command"], 'timeout_seconds': timeout_seconds}

    async def run(self, command: str, timeout_seconds: float) -> str:
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
            output = stdout.decode('utf-8').rstrip('\n')
            if process.returncode != 0:
                raise ToolError(output)
            return output
        except asyncio.TimeoutError:
            raise ToolError(f"Command timed out after {timeout_seconds} seconds") from None
