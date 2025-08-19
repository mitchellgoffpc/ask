import ast
import asyncio
import atexit
import io
import os
import queue
import signal
import traceback
from contextlib import redirect_stdout, redirect_stderr
from multiprocessing import Queue, Process
from typing import Any

from ask.prompts import load_tool_prompt
from ask.tools.base import ToolError, Tool, Parameter

# NOTE: It would be great if we could just use a thread for this, but as far as I know
# there's no way to capture stdout/stderr without interfering with the main thread.
def repl_worker(command_queue: Queue, result_queue: Queue) -> None:
    def signal_handler(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, signal_handler)
    globals_dict: dict[str, Any] = {}
    while (nodes := command_queue.get()) is not None:
        try:
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
                        exec(code, globals_dict)
                    except KeyboardInterrupt:
                        break
                    except SystemExit:
                        globals_dict.clear()
                        break
                    except BaseException as e:
                        captured_traceback = ''.join(traceback.format_exception(type(e), e, e.__traceback__.tb_next if e.__traceback__ else None))
                        break

            result_queue.put((captured_output.getvalue(), captured_error.getvalue(), captured_traceback))
        except Exception as e:
            result_queue.put(("", str(e), None))


class PythonTool(Tool):
    name = "Python"
    description = load_tool_prompt('python')
    parameters = [
        Parameter("code", "string", "The Python code to execute"),
        Parameter("timeout", "number", "Optional timeout in milliseconds (max 600000)", required=False),
        Parameter("description", "string", "Clear, concise description of what this code does in 5-10 words", required=False)]

    def __init__(self) -> None:
        self.command_queue: Queue = Queue()
        self.result_queue: Queue = Queue()
        self.worker_process: Process | None = None

    def _interrupt_worker(self) -> None:
        if self.worker_process and self.worker_process.pid:
            try:
                os.kill(self.worker_process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass

    def _cleanup_worker(self) -> None:
        try:
            if self.worker_process and self.worker_process.is_alive():
                self.command_queue.put(None)
                self.worker_process.join(timeout=1.0)
        except Exception:
            pass

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
        if not self.worker_process:
            self.worker_process = Process(target=repl_worker, args=(self.command_queue, self.result_queue), daemon=True)
            self.worker_process.start()
            atexit.register(self._cleanup_worker)

        while True:  # Drain the result queue
            try: self.result_queue.get_nowait()
            except queue.Empty: break

        try:
            module = ast.parse(args['code'], '<string>')
            nodes = list(module.body)
        except SyntaxError as e:
            raise ToolError(f"Failed to compile code: {e}") from e
        except (ValueError, OverflowError) as e:
            raise ToolError(f"Code contains invalid literal: {e}") from e

        timeout = int(args.get("timeout", 120000)) / 1000.0  # Convert to seconds
        if timeout > 600:
            raise ToolError("Timeout cannot exceed 600000ms (10 minutes)")

        self.command_queue.put(nodes)
        try:
            stdout, stderr, traceback = await asyncio.to_thread(self.result_queue.get, timeout=timeout)
        except queue.Empty:
            self._interrupt_worker()
            raise ToolError(f"Code execution timed out after {timeout}s") from None
        except asyncio.CancelledError:
            self._interrupt_worker()
            raise

        stdout_formatted = f'<python-stdout>\n{stdout}</python-stdout>'
        stderr_formatted = f'<python-stderr>\n{stderr}{traceback or ""}</python-stderr>'
        return f'{stdout_formatted}\n{stderr_formatted}'
