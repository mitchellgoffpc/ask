import readline
from pathlib import Path
from ask.query import query
from ask.models import MODELS, MODEL_SHORTCUTS, Prompt, Model
from ask.edit import EDIT_SYSTEM_PROMPT, print_diff, apply_section_edit, extract_code_blocks

# Tab completion

def common_prefix(strings: list[str]) -> str:
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
    return prefix

def complete(text: str, state: int) -> str | None:
    file_commands = ('.file', ':file', ':f')
    buffer = readline.get_line_buffer()
    cmd, *args = buffer.lstrip().split()
    if cmd.lower() in file_commands:
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

def attach_file(arg: str, prompt: Prompt, attached_files: dict[Path, str]) -> Prompt:
    file_paths = arg.split()
    for file_path in file_paths:
        path = Path(file_path).expanduser()
        if path.exists():
            content = path.read_text().strip()
            attached_files[path] = content
            prompt.append({'role': 'user', 'content': f"I'm attaching the following file to our converstaion:\n\n{path}\n```\n{content}\n```"})
            prompt.append({'role': 'assistant', 'content': f"Successfully attached {path}."})
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


# Ask / Edit

def ask(prompt: Prompt, model: Model, user_input: str, system_prompt: str, attached_files: dict[Path, str]) -> str:
    context = []
    for path, original_content in {Path(p).expanduser(): c for p, c in attached_files.items()}.items():
        content = path.read_text().strip()
        if content != original_content:
            context.append(f'{path}\n```\n{content}\n```')

    context_str = ''
    if context:
        context_str = '\n\n'.join(context)
        context_str = f"Here are the most up-to-date versions of my attached files:\n\n{context_str}\n\n"

    # DEBUGGING
    import json
    with open('/tmp/chat.json', 'w') as f:
        json.dump([*prompt, {'role': 'user', 'content': context_str + user_input}], f, indent=2)

    chunks = []
    for chunk in query(prompt + [{'role': 'user', 'content': context_str + user_input}], model, system_prompt=system_prompt):
        chunks.append(chunk)
        print(chunk, end='', flush=True)
    return ''.join(chunks)

def edit(response: str) -> dict[Path, str]:
    modifications = {}
    for file_path_str, code_block in extract_code_blocks(response):
        file_path = Path(file_path_str).expanduser()
        file_exists = file_path.exists()
        if file_exists:
            file_data = file_path.read_text()
            modified = apply_section_edit(file_data, code_block)
            user_prompt = f"Do you want to apply this edit to {file_path}? (y/n): "
        else:
            file_data = ""
            modified = code_block
            user_prompt = f"File {file_path} does not exist. Do you want to create it? (y/n): "

        print_diff(file_data, modified, file_path)
        user_input = input(user_prompt).strip().lower()
        if user_input == 'y':
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(modified)
            print(f"Saved edits to {file_path}" if file_exists else f"Created {file_path}")
            modifications[file_path] = modified

    return modifications


# Main chat loop

def chat(prompt: Prompt, model: Model, system_prompt: str) -> None:
    history_file = Path.home() / '.ask_history'
    history_file.touch(exist_ok=True)

    readline.set_completer_delims(' \t\n/;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(complete)
    readline.read_history_file(str(history_file))
    readline.set_history_length(1000)

    prompt = [msg for msg in prompt if msg['content']]
    attached_files: dict[Path, str] = {}

    while True:
        try:
            user_input = input("> ")
            if not user_input.strip():
                continue
            readline.write_history_file(str(history_file))

            cmd = user_input.lower().strip().split()[0] if user_input.strip() else ''
            arg = user_input[len(cmd):].strip()

            if cmd in ('exit', 'quit', '.exit', '.quit', ':exit', ':quit', ':q'):
                return
            elif cmd in ('.models', ':models'):
                show_models()
            elif cmd in ('.model', ':model', ':m'):
                model = switch_model(arg, model)
            elif cmd in ('.file', ':file', ':f'):
                prompt = attach_file(arg, prompt, attached_files)
            elif cmd in ('.files', ':files'):
                show_files(attached_files)
            elif cmd in ('.edit', ':edit', ':e'):
                response = ask(prompt, model, arg, EDIT_SYSTEM_PROMPT, attached_files)
                modifications = edit(response)
                if modifications:
                    prompt.append({'role': 'user', 'content': arg})
                    prompt.append({'role': 'assistant', 'content': response})
            else:
                response = ask(prompt, model, user_input, system_prompt, attached_files)
                prompt.append({'role': 'user', 'content': user_input})
                prompt.append({'role': 'assistant', 'content': response})

        except KeyboardInterrupt:
            print()
            return
