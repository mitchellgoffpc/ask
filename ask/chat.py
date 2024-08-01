import readline  # noqa: F401
from pathlib import Path
from ask.query import query
from ask.models import MODELS, MODEL_SHORTCUTS, Prompt, Model

def chat(prompt: Prompt, model: Model, system_prompt: str):
    prompt = [msg for msg in prompt if msg['content']]
    attached_files = {}
    while True:
        try:
            user_input = input("> ")
            cmd = user_input.lower().strip()
            cmd = cmd.split()[0] if cmd else ''
            if cmd in ('exit', 'quit', '.exit', '.quit', ':exit', ':quit', ':q'):
                return
            elif cmd in ('.models', ':models'):
                print("Available models:")
                for m in MODELS:
                    print(f"- {m.name} ({', '.join(m.shortcuts)})")
            elif cmd in ('.model', ':model', ':m'):
                model_name = user_input[len(cmd + ' '):].strip()
                if not model_name:
                    print(f"Current model is {model.name}.")
                elif model_name in MODEL_SHORTCUTS:
                    model = MODEL_SHORTCUTS[model_name]
                    print(f"Model switched to {model.name}.")
                else:
                    print(f"Model {model_name!r} not found.")
            elif cmd in ('.file', ':file', ':f'):
                file_paths = user_input[len(cmd + ' '):].strip().split()
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
            elif cmd in ('.files', ':files'):
                if attached_files:
                    print("Attached files:")
                    for path in attached_files:
                        print(f"- {path}")
                else:
                    print("No files attached.")
            else:
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

        except KeyboardInterrupt:
            print()
            return
