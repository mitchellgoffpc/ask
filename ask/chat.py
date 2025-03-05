import readline
import subprocess
from pathlib import Path
from ask.tools import Tool
from ask.query import act
from ask.models import MODELS, MODEL_SHORTCUTS, Model, Message, Text, Image

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

def attach_file(arg: str, messages: list[Message], attached_files: dict[Path, str]) -> list[Message]:
    file_paths = arg.split()
    for file_path in file_paths:
        path = Path(file_path).expanduser()
        if path.exists():
            content = path.read_text().strip()
            attached_files[path] = content
            messages.append(Message(role='user', content=[Text(f"I'm attaching the following file to our conversation:\n\n{path}\n```\n{content}\n```")]))
            messages.append(Message(role='assistant', content=[Text(f"Successfully attached {path}.")]))
            print(f"File {path} added to context.")
        else:
            print(f"File {path} not found.")
    return messages

def show_files(attached_files: dict[Path, str]) -> None:
    if attached_files:
        print("Attached files:")
        for path in attached_files:
            print(f"- {path}")
    else:
        print("No files attached.")


# Main chat loop

def chat(model: Model, question: str, tools: list[Tool], files: dict[str, Text | Image], system_prompt: str) -> None:
    history_file = Path.home() / '.ask_history'
    history_file.touch(exist_ok=True)

    readline.set_completer_delims(' \t\n/;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(complete)
    readline.read_history_file(str(history_file))
    readline.set_history_length(1000)

    messages = []
    attached_files: dict[Path, str] = {}
    image_content = [content for content in files.values() if isinstance(content, Image)]
    if question.strip() or image_content:
        messages.append(Message(role='user', content=[*image_content, Text(question)]))
        messages = act(model, messages, tools, system_prompt)

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
                        print(result.stderr.rstrip('\n'))
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
                messages = attach_file(arg, messages, attached_files)
            elif cmd.startswith('/'):
                print("Invalid command. Type /help for a list of commands.")
            else:
                messages.append(Message(role='user', content=[Text(user_input)]))
                messages = act(model, messages, tools, system_prompt)

        except KeyboardInterrupt:
            print()
            return
