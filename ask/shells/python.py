from __future__ import annotations
import ast
import asyncio
import atexit
import io
import os
import queue
import signal
import traceback
from contextlib import redirect_stdout, redirect_stderr, suppress
from multiprocessing import Queue, Process
from typing import Any


def repl_worker(command_queue: Queue[list[ast.stmt] | None], result_queue: Queue[tuple[str, str] | None]) -> None:
    def signal_handler(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)
    globals_dict: dict[str, Any] = {}
    while True:
        try:
            result_queue.put(None)
            if (nodes := command_queue.get()) is None:
                break
            captured_output = io.StringIO()
            captured_traceback = ''

            # Redirect both stdout and stderr to the same stream
            with redirect_stdout(captured_output), redirect_stderr(captured_output):
                for i, node in enumerate(nodes):
                    if i == len(nodes) - 1 and isinstance(node, ast.Expr):
                        code = compile(ast.Interactive([node]), '<stdin>', 'single')
                    else:
                        code = compile(ast.Module([node], []), '<stdin>', 'exec')

                    try:
                        exec(code, globals_dict)  # noqa: S102
                    except KeyboardInterrupt:
                        break
                    except SystemExit:
                        globals_dict.clear()
                        break
                    except BaseException as e:
                        traceback_lines = traceback.format_exception(type(e), e, e.__traceback__)
                        captured_traceback = ''.join(traceback_lines[:1] + traceback_lines[2:])
                        break
            result_queue.put((captured_output.getvalue(), captured_traceback))
        except BaseException as e:
            traceback_lines = traceback.format_exception(type(e), e, e.__traceback__)
            captured_traceback = ''.join(traceback_lines[:1] + traceback_lines[2:])
            result_queue.put(("", captured_traceback))


class PythonShell:
    def __init__(self) -> None:
        self.command_queue: Queue[list[ast.stmt] | None] = Queue()
        self.result_queue: Queue[tuple[str, str] | None] = Queue()
        self.worker_process: Process | None = None

    async def _interrupt_worker(self) -> None:
        if self.worker_process and self.worker_process.pid:
            with suppress(ProcessLookupError):
                os.kill(self.worker_process.pid, signal.SIGINT)

    def _cleanup_worker(self) -> None:
        with suppress(Exception):
            if self.worker_process and self.worker_process.is_alive():
                self.command_queue.put(None)
                self.worker_process.join(timeout=1.0)

    def parse(self, code: str) -> list[ast.stmt]:
        module = ast.parse(code, '<string>')
        return list(module.body)

    async def execute(self, nodes: list[ast.stmt], timeout_seconds: float) -> tuple[str, str]:
        if not self.worker_process:
            self.worker_process = Process(target=repl_worker, args=(self.command_queue, self.result_queue), daemon=True)
            self.worker_process.start()
            atexit.register(self._cleanup_worker)

        while True:
            try:
                if self.result_queue.get_nowait() is None:
                    break
            except queue.Empty:
                await asyncio.sleep(0.01)

        self.command_queue.put(nodes)
        start_time = asyncio.get_event_loop().time()
        while True:
            try:
                try:
                    result = self.result_queue.get_nowait()
                    assert result is not None
                    output, exception = result
                    break
                except queue.Empty:
                    if asyncio.get_event_loop().time() - start_time >= timeout_seconds:
                        await self._interrupt_worker()
                        raise TimeoutError(f"Code execution timed out after {timeout_seconds} seconds") from None
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                await self._interrupt_worker()
                raise

        return output, exception
