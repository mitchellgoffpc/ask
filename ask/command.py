import os
import re
import sys
import pty
import select
import subprocess

def read_all(*fds):
    parts = []
    rlist, _, _ = select.select(fds, [], [], 0.01)
    for f in rlist:
        output = os.read(f, 1000)
        sys.stdout.write(output.decode("utf-8"))
        sys.stdout.flush()
        parts.append(output.decode('utf-8'))
    return ''.join(parts)

def extract_command(response: str) -> tuple[str, str]:
    if (match := re.search(r'<execute language="(.*?)" shell="(.*?)">(.*?)</execute>', response, re.DOTALL)):
        language, shell, command = match.groups()
        return "bash" if shell == "true" else language, command.strip()
    else:
        return '', ''

def execute_command(command_type: str, command: str) -> str:
    try:
        if command_type == 'bash':
            args = ['bash', '--login', '-c', command]
        elif command_type == 'python':
            args = ['python', '-c', command]
        else:
            raise Exception(f"Unrecognized command type: {command_type!r}")

        stdout_master_fd, stdout_slave_fd = pty.openpty()
        stderr_master_fd, stderr_slave_fd = pty.openpty()
        process = subprocess.Popen(args, stdout=stdout_slave_fd, stderr=stderr_slave_fd, close_fds=True)

        output_parts = []
        while process.poll() is None:
            output_parts.append(read_all(stdout_master_fd, stderr_master_fd))
        output_parts.append(read_all(stdout_master_fd, stderr_master_fd))

        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)
        print()
        return ''.join(output_parts).strip()

    except subprocess.CalledProcessError as e:
        return f"Error: Command exited with status {e.returncode}"
