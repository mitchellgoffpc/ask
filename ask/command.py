import re
import sys
import subprocess

COMMAND_SYSTEM_PROMPT = """
You are being run in an interactive scaffold with access to the system's bash shell and python interpreter. Whenever you want to access these tools, you should reply with a message containing a single shell command, written in a <bash> XML tag, or a python code snippet, written in a <python> XML tag. Remember to use the XML rather than backticks. You will be shown the result of the command or code execution and be able to run more commands or code. Other things you say will be sent to the user. In cases where you know how to do something, don't explain how to do it, just start doing it by emitting bash commands or python code one at a time. Remember that you can't interact with stdin directly, so if you want to e.g. do things over ssh you need to run commands that will finish and return control to you rather than blocking on stdin. Don't wait for the user to say okay before suggesting a command or code to run. If possible, don't include explanation, just provide the command or code. Note that all commands will be run in a fresh bash instance, so you need to e.g. cd between commands if you want to run them in the same directory.
"""

def extract_command(response: str) -> tuple[str, str]:
    if (bash_match := re.search(r'<bash>(.*?)</bash>', response, re.DOTALL)):
        return 'bash', bash_match.group(1).strip()
    elif (python_match := re.search(r'<python>(.*?)</python>', response, re.DOTALL)):
        return 'python', python_match.group(1).strip()
    else:
        return '', ''

def execute_command(command_type: str, command: str, tee: bool = False) -> str:
    try:
        if command_type == 'bash':
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        elif command_type == 'python':
            process = subprocess.Popen(['python', '-c', command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            raise Exception(f"Unrecognized command type: {command_type!r}")

        assert process.stdout is not None and process.stderr is not None
        if tee:
            print("\nCommand output:")

        output = []
        while True:
            while (stdout_line := process.stdout.readline()):
                if tee:
                    print(stdout_line.strip())
                output.append(stdout_line)
            while (stderr_line := process.stderr.readline()):
                if tee:
                    print(stderr_line.strip(), file=sys.stderr)
                output.append(stderr_line)
            if process.poll() is not None:
                break

        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)
        return ''.join(output).strip()

    except subprocess.CalledProcessError as e:
        return f"Error: Command exited with status {e.returncode}"
