import asyncio
from typing import Any

from ask.prompts import load_tool_prompt, dedent
from ask.tools.base import ToolError, Tool, Parameter

class BashTool(Tool):
    name = "Bash"
    description = load_tool_prompt('bash')
    needs_approval = True
    parameters = [
        Parameter("command", "string", "The command to execute"),
        Parameter("timeout", "number", "Optional timeout in milliseconds (max 600000)", required=False),
        Parameter("description", "string", dedent("""
            Clear, concise description of what this command does in 5-10 words. Examples:
            Input: ls\nOutput: Lists files in current directory\n
            Input: git status\nOutput: Shows working tree status\n
            Input: npm install\nOutput: Installs package dependencies\n
            Input: mkdir foo\nOutput: Creates directory 'foo'""", keep_newlines=True), required=False)]

    def render_args(self, args: dict[str, str]) -> str:
        description = args.get('description', '')
        if description:
            return f"{description}: {args['command']}"
        return args['command']

    def render_short_response(self, response: str) -> str:
        lines = response.strip().split('\n')
        if len(lines) <= 1:
            return "Command executed successfully"
        return f"Command executed ({len(lines)} lines output)"

    def check(self, args: dict[str, Any]) -> dict[str, Any]:
        args = super().check(args)
        timeout_seconds = args.get("timeout", 120000) / 1000.0  # Default 2 minutes
        if timeout_seconds > 600:
            raise ToolError("Timeout cannot exceed 600000ms (10 minutes)")
        return {'command': args["command"], 'timeout_seconds': timeout_seconds}

    async def run(self, command: str, timeout_seconds: float) -> str:
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
            stdout_text = f"<bash-stdout>\n{stdout.decode('utf-8')}</bash-stdout>"
            stderr_text = f"<bash-stderr>\n{stderr.decode('utf-8')}</bash-stderr>"
            return f"{stdout_text}\n{stderr_text}"
        except asyncio.TimeoutError:
            raise ToolError(f"Command timed out after {timeout_seconds} seconds") from None
