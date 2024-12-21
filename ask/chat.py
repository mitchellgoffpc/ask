import readline
from pathlib import Path
import subprocess
from ask.query import query_text
from ask.edit import apply_edits
from ask.command import extract_command, execute_command
from ask.models import MODELS, MODEL_SHORTCUTS, Text, Message, Model

# Tab completion

def common_prefix(strings: list[str]) -> str:
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
    return prefix

def complete(text: str, state: int) -> str | None:
    buffer = readline.get_line_buffer()
    cmd, *args = buffer.lstrip().split()
    if cmd.lower() in ('/file', '/f'):
        path = Path(args[-1])
        if not text:
            matches = path.expanduser().glob('*')
        else:
            matches = path.parent.expanduser().glob(path.name + '*')
        completions = [f"{p.name}{'/' if p.is_dir() else ''}" for p in matches]
        if len(completions) > 1:
            common = common_prefix(completions)
            if common != text and state == 0:
                return common
        return (completions + [None])[state]
    return None


# Commands

def show_help() -> None:
    print("Available commands:")
    print("  /help - Show this help message")
    print("  /models - Show available models")
    print("  /model <name> - Switch to a different model")
    print("  /files - Show attached files")
    print("  /file <path> - Attach a file to the conversation")
    print("  /exit or /quit - Exit the chat")
    print("  !<command> - Execute a shell command")


def show_models() -> None:
    print("Available models:")
    for m in MODELS:
        print(f"- {m.name} ({', '.join(m.shortcuts)})")

def switch_model(arg: str, model: Model) -> Model:
    if not arg:
        print(f"Current model is {model.name}.")
    elif arg in MODEL_SHORTCUTS:
        model = MODEL_SHORTCUTS[arg]
        print(f"Model switched to {model.name}.")
    else:
        print(f"Model {arg!r} not found.")
    return model

def attach_file(arg: str, prompt: list[Message], attached_files: dict[Path, str]) -> list[Message]:
    file_paths = arg.split()
    for file_path in file_paths:
        path = Path(file_path).expanduser()
        if path.exists():
            content = path.read_text().strip()
            attached_files[path] = content
            prompt.append(Message(role='user', content=[Text(f"I'm attaching the following file to our converstaion:\n\n{path}\n```\n{content}\n```")]))
            prompt.append(Message(role='assistant', content=[Text(f"Successfully attached {path}.")]))
            print(f"File {path} added to context.")
        else:
            print(f"File {path} not found.")
    return prompt

def show_files(attached_files: dict[Path, str]) -> None:
    if attached_files:
        print("Attached files:")
        for path in attached_files:
            print(f"- {path}")
    else:
        print("No files attached.")


# Query

def ask(prompt: list[Message], model: Model, user_input: str, system_prompt: str, attached_files: dict[Path, str]) -> str:
    context = []
    for path, original_content in {Path(p).expanduser(): c for p, c in attached_files.items()}.items():
        content = path.read_text().strip()
        if content != original_content:
            context.append(f'{path}\n```\n{content}\n```')

    context_str = ''
    if context:
        context_str = '\n\n'.join(context)
        context_str = f"Here are the most up-to-date versions of my attached files:\n\n{context_str}\n\n"

    chunks = []
    user_message = Message(role='user', content=[Text(context_str + user_input)])
    for chunk in query_text([*prompt, user_message], model, system_prompt=system_prompt):
        chunks.append(chunk)
        print(chunk, end='', flush=True)
    print()
    return ''.join(chunks)

def act(prompt: list[Message], model: Model, system_prompt: str, attached_files: dict[Path, str]) -> list[Message]:
    while True:
        assert prompt and prompt[-1].role == 'user'
        response = ask(prompt[:-1], model, prompt[-1].content[-1]['text'], system_prompt, attached_files)  # type: ignore
        prompt.append(Message(role='assistant', content=[Text(response)]))

        apply_edits(response)
        command_type, command = extract_command(response)
        if command:
            result = execute_command(command_type, command)
            prompt.append(Message(role='assistant', content=[Text(f"Command output:\n{result}")]))
        else:
            return prompt


# Main chat loop

def chat(prompt: list[Message], model: Model, system_prompt: str) -> None:
    history_file = Path.home() / '.ask_history'
    history_file.touch(exist_ok=True)

    readline.set_completer_delims(' \t\n/;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(complete)
    readline.read_history_file(str(history_file))
    readline.set_history_length(1000)

    prompt = [msg for msg in prompt if msg.content]
    attached_files: dict[Path, str] = {}

    if prompt and prompt[-1].role == 'user':
        prompt = act(prompt, model, system_prompt, attached_files)

    while True:
        try:
            user_input = input("> ")
            if not user_input.strip():
                continue
            readline.write_history_file(str(history_file))

            # Shell command
            if user_input.startswith('!'):
                try:
                    result = subprocess.run(user_input[1:], shell=True, check=True, text=True, capture_output=True)
                    print(result.stdout.rstrip('\n'))
                    if result.stderr:
                        print(result.stdout.rstrip('\n'))
                except subprocess.CalledProcessError as e:
                    print(f"Command failed with exit code {e.returncode}")
                    print(e.stderr)
                continue

            cmd = user_input.lower().strip().split()[0] if user_input.strip() else ''
            arg = user_input[len(cmd):].strip()

            # Commands
            if cmd in ('/exit', '/quit', '/q'):
                return
            elif cmd in ('/help', '/h'):
                show_help()
            elif cmd in ('/models',):
                show_models()
            elif cmd in ('/model', '/m'):
                model = switch_model(arg, model)
            elif cmd in ('/files',):
                show_files(attached_files)
            elif cmd in ('/file', '/f'):
                prompt = attach_file(arg, prompt, attached_files)
            elif cmd.startswith('/'):
                print("Invalid command. Type /help for a list of commands.")
            else:
                prompt.append(Message(role='user', content=[Text(user_input)]))
                prompt = act(prompt, model, system_prompt, attached_files)

        except KeyboardInterrupt:
            print()
            return
