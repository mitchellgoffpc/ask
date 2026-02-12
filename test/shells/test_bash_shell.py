import asyncio
import tempfile
import unittest

from ask.shells.bash import BashShell


class TestBashShell(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.shell = BashShell()

    def tearDown(self) -> None:
        if self.shell:
            self.shell._cleanup()  # noqa: SLF001

    async def test_basic_execution(self) -> None:
        stdout, stderr = await self.shell.execute("echo 'hello world'", 10)
        self.assertEqual("hello world", stdout)
        self.assertEqual("", stderr)

    async def test_command_output(self) -> None:
        stdout, stderr = await self.shell.execute("expr 2 + 2")
        self.assertEqual("4", stdout)
        self.assertEqual("", stderr)

    async def test_stderr_output(self) -> None:
        stdout, stderr = await self.shell.execute("echo 'error message' >&2")
        self.assertEqual("", stdout)
        self.assertEqual("error message", stderr)

    async def test_variable_persistence(self) -> None:
        await self.shell.execute("export TEST_VAR=42")
        stdout, stderr = await self.shell.execute("echo $TEST_VAR")
        self.assertEqual("42", stdout)
        self.assertEqual("", stderr)

    async def test_multiline_command(self) -> None:
        command = "for i in {1..3}; do echo \"Count: $i\"; done"
        stdout, stderr = await self.shell.execute(command)
        self.assertEqual("Count: 1\nCount: 2\nCount: 3", stdout)
        self.assertEqual("", stderr)

    async def test_large_output(self) -> None:
        stdout, _ = await self.shell.execute("seq 1 1000")
        lines = stdout.strip().split('\n')
        self.assertEqual(len(lines), 1000)
        self.assertEqual(lines[0], "1")
        self.assertEqual(lines[-1], "1000")

    async def test_working_directory_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            await self.shell.execute(f"mkdir -p {temp_dir}/test_dir")
            await self.shell.execute(f"cd {temp_dir}/test_dir")
            stdout, _ = await self.shell.execute("pwd")
            self.assertIn(f"{temp_dir}/test_dir", stdout)
            await self.shell.execute(f"cd {temp_dir} && rm -rf test_dir")

    async def test_error_handling(self) -> None:
        _, stderr = await self.shell.execute("nonexistent_command")
        self.assertIn("command not found", stderr)

    async def test_timeout(self) -> None:
        start_time = asyncio.get_event_loop().time()
        with self.assertRaises(TimeoutError) as context:
            await self.shell.execute("sleep 10", 0.1)
        self.assertIn("Command execution timed out", str(context.exception))
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)

    async def test_shell_after_timeout_recovery(self) -> None:
        start_time = asyncio.get_event_loop().time()
        with self.assertRaises(TimeoutError):
            await self.shell.execute("sleep 10", 0.1)

        stdout, _ = await self.shell.execute("echo 'recovery test'")
        self.assertIn("recovery test", stdout)
        self.assertLess(asyncio.get_event_loop().time() - start_time, 1.0)
