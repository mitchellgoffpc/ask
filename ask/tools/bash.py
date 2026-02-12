import asyncio
import os
import signal
from typing import Any

from ask.messages import Blob, Text
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

    def check(self, args: dict[str, Any]) -> None:
        super().check(args)
        if 'timeout' in args and args['timeout'] > 600000:
            raise ToolError("Timeout cannot exceed 600000ms (10 minutes)")

    async def run(self, args: dict[str, Any], artifacts: dict[str, Any]) -> Blob:
        command = args['command']
        timeout_seconds = args.get("timeout", 120000) / 1000.0
        process = None
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
            output = stdout.decode('utf-8').rstrip('\n')
            if process.returncode != 0:
                raise ToolError(output)
            return Text(output)
        except TimeoutError:
            raise ToolError(f"Command timed out after {timeout_seconds} seconds") from None
        finally:
            if process and process.returncode is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                await process.wait()
