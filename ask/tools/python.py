import ast
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Any

from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter


class PythonTool(Tool):
    name = "Python"
    description = load_tool_prompt('python')
    parameters = [
        Parameter("code", "string", "The Python code to execute"),
        Parameter("timeout", "number", "Optional timeout in milliseconds (max 600000)", required=False),
        Parameter("description", "string", "Clear, concise description of what this code does in 5-10 words", required=False)]

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.locals: dict[str, Any] = {}

    def render_args(self, args: dict[str, str]) -> str:
        description = args.get('description', '')
        if description:
            return description
        code_snippet = args['code'][:50]
        if len(args['code']) > 50:
            code_snippet += "..."
        return code_snippet

    def render_short_response(self, response: str) -> str:
        lines = response.strip().split('\n')
        if len(lines) <= 3:
            return response.strip()
        return f"Python output ({len(lines)} lines)"

    async def run(self, args: dict[str, Any]) -> str:
        try:
            module = ast.parse(args['code'], '<string>')
            nodes = list(module.body)
        except SyntaxError as e:
            raise ToolError(f"Failed to compile code: {e}") from e
        except (ValueError, OverflowError) as e:
            raise ToolError(f"Code contains invalid literal: {e}") from e

        timeout = int(args.get("timeout", 120000))
        if timeout > 600000:
            raise ToolError("Timeout cannot exceed 600000ms (10 minutes)")

        captured_output = io.StringIO()
        captured_error = io.StringIO()
        captured_traceback = None
        with redirect_stdout(captured_output), redirect_stderr(captured_error):
            for i, node in enumerate(nodes):
                if i == len(nodes) - 1 and isinstance(node, ast.Expr):
                    code = compile(ast.Interactive([node]), '<stdin>', 'single')
                else:
                    code = compile(ast.Module([node], []), '<stdin>', 'exec')

                try:
                    exec(code, self.locals)
                except SystemExit:
                    self.reset()
                    break
                except BaseException as e:
                    captured_traceback = ''.join(traceback.format_exception(type(e), e, e.__traceback__.tb_next if e.__traceback__ else None))
                    break

        stdout = f'<python-stdout>\n{captured_output.getvalue()}</python-stdout>'
        stderr = f'<python-stderr>\n{captured_error.getvalue()}{captured_traceback or ""}</python-stderr>'
        return f'{stdout}\n{stderr}'
