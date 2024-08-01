import readline  # noqa: F401
from pathlib import Path
from ask.query import query
from ask.models import MODELS, MODEL_SHORTCUTS, Prompt, Model

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


# Query

def get_chat_response(user_input: str, prompt: Prompt, model: Model, system_prompt: str, attached_files: dict[Path, str]) -> Prompt:
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
    for chunk in query([*prompt, {'role': 'user', 'content': context_str + user_input}], model, system_prompt=system_prompt):
        chunks.append(chunk)
        print(chunk, end='', flush=True)
    prompt.append({'role': 'user', 'content': user_input})
    prompt.append({'role': 'assistant', 'content': ''.join(chunks)})
    return prompt


# Main chat loop

def chat(prompt: Prompt, model: Model, system_prompt: str) -> None:
    prompt = [msg for msg in prompt if msg['content']]
    attached_files: dict[Path, str] = {}
    while True:
        try:
            user_input = input("> ")
            if not user_input.strip():
                continue

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
            else:
                prompt = get_chat_response(user_input, prompt, model, system_prompt, attached_files)

        except KeyboardInterrupt:
            print()
            return
