import os
import re
import sys
import pty
import select
import subprocess

COMMAND_SYSTEM_PROMPT = """
You are being run in an interactive scaffold with access to the system's bash shell and python interpreter. Whenever you want to access these tools, you should reply with a message containing a single shell command, written in a <bash> XML tag, or a python code snippet, written in a <python> XML tag. Remember to use the XML rather than backticks. You will be shown the result of the command or code execution and be able to run more commands or code. Other things you say will be sent to the user. In cases where you know how to do something, don't explain how to do it, just start doing it by emitting bash commands or python code one at a time. Remember that you can't interact with stdin directly, so if you want to e.g. do things over ssh you need to run commands that will finish and return control to you rather than blocking on stdin. Don't wait for the user to say okay before suggesting a command or code to run. If possible, don't include explanation, just provide the command or code. Note that all commands will be run in a fresh bash instance, so you need to e.g. cd between commands if you want to run them in the same directory.
"""

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
    if (bash_match := re.search(r'<bash>(.*?)</bash>', response, re.DOTALL)):
        return 'bash', bash_match.group(1).strip()
    elif (python_match := re.search(r'<python>(.*?)</python>', response, re.DOTALL)):
        return 'python', python_match.group(1).strip()
    else:
        return '', ''

def execute_command(command_type: str, command: str) -> str:
    try:
        if command_type == 'bash':
            args = [command]
            shell = True
        elif command_type == 'python':
            args = ['python', '-c', command]
            shell = False
        else:
            raise Exception(f"Unrecognized command type: {command_type!r}")

        stdout_master_fd, stdout_slave_fd = pty.openpty()
        stderr_master_fd, stderr_slave_fd = pty.openpty()
        process = subprocess.Popen(args, shell=shell, stdout=stdout_slave_fd, stderr=stderr_slave_fd, close_fds=True)

        output_parts = []
        while process.poll() is None:
            output_parts.append(read_all(stdout_master_fd, stderr_master_fd))
        output_parts.append(read_all(stdout_master_fd, stderr_master_fd))

        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)
        return ''.join(output_parts).strip()

    except subprocess.CalledProcessError as e:
        return f"Error: Command exited with status {e.returncode}"
