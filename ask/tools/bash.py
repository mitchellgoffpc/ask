import subprocess
from typing import Any
from ask.tools.base import Tool, Parameter

class BashTool(Tool):
    name = "bash"
    description = "Execute a bash command on the user's system."
    parameters = [Parameter("command", "string", "The bash command to execute.")]

    def run(self, args: dict[str, Any]) -> str:
        try:
            result = subprocess.run(args["command"], shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.stdout.decode('utf-8')
        except subprocess.CalledProcessError as e:
            return f"An error occurred: {e.stderr.decode('utf-8')}"
