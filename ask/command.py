import os
import re
import sys
import pty
import select
import subprocess

def detect_user_platform() -> str:
    if sys.platform.startswith('linux'):
        return 'linux'
    elif sys.platform == 'darwin':
        return 'mac'
    elif sys.platform.startswith('win'):
        return 'windows'
    else:
        return sys.platform

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
    pattern = r'### EXECUTE(?: \((.*?)\))?\s+```(.*?)\n(.*?)\n```'
    matches = re.finditer(pattern, response, re.DOTALL)
    user_platform = detect_user_platform()

    for match in matches:
        platforms_str, language, command = match.groups()
        platforms = [p.strip().lower() for p in platforms_str.split('/')] if platforms_str else None
        if platforms is None or user_platform in platforms:
            return language.strip(), command.strip()

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
