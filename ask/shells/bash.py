import asyncio
import atexit
import io
import os
import select
import subprocess
import uuid


class BashShell:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.prompt = f"PROMPT_{uuid.uuid4()}"

    def _cleanup(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self.process.kill()
                    self.process.wait(timeout=1.0)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    pass
            self.process = None

    def _is_ready(self, fd: int) -> bool:
        ready, _, _ = select.select([fd], [], [], 0)
        return bool(ready)

    async def execute(self, command: str, timeout_seconds: float = 120.0) -> tuple[str, str]:
        if self.process is None:
            self.process = subprocess.Popen(["/bin/bash"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            atexit.register(self._cleanup)

        assert self.process.stdin and self.process.stdout and self.process.stderr
        self.process.stdin.write(f"{command}\n")
        self.process.stdin.write(f"echo {self.prompt}\n")
        self.process.stdin.flush()

        stdout = io.StringIO()
        stderr = io.StringIO()
        stdout_fd = self.process.stdout.fileno()
        stderr_fd = self.process.stderr.fileno()
        start_time = asyncio.get_event_loop().time()
        os.set_blocking(stdout_fd, False)
        os.set_blocking(stderr_fd, False)

        while True:
            if asyncio.get_event_loop().time() - start_time >= timeout_seconds:
                self._cleanup()
                raise TimeoutError(f"Command execution timed out after {timeout_seconds} seconds")

            try:
                while self._is_ready(stdout_fd):
                    stdout.write(os.read(stdout_fd, 1024).decode())
                while self._is_ready(stderr_fd):
                    stderr.write(os.read(stderr_fd, 1024).decode())
                if stdout.getvalue().rstrip('\n').endswith(self.prompt):
                    return stdout.getvalue().rstrip('\n').removesuffix(self.prompt).rstrip('\n'), stderr.getvalue().rstrip('\n')
            except OSError:
                return stdout.getvalue().rstrip('\n').removesuffix(self.prompt).rstrip('\n'), stderr.getvalue().rstrip('\n')
            await asyncio.sleep(0.01)
