import sys
import json
from pathlib import Path

PROMPT_DIR = Path(__file__).parent

if __name__ == '__main__':
    with open(sys.argv[1]) as f:
        data = json.load(f)

    with open(PROMPT_DIR / "system.toml", "w") as f:
        f.write('prompt = """\n')
        for msg in data['body']['system']:
            f.write(msg['text'].strip().replace(" \n", "\n"))
        f.write('\n"""\n')

    (PROMPT_DIR / 'tools').mkdir(exist_ok=True)
    for tool in data['body']['tools']:
        with open(PROMPT_DIR / 'tools' / f"{tool['name']}.toml", "w") as f:
            description = tool["description"].strip().replace(' \n', '\n').replace(' \n', '\n').replace('\\', '\\\\')
            f.write(f'name = "{tool["name"]}"\n')
            f.write(f'description = """\n{description}\n"""\n\n')
            f.write(f'parameters = """\n{json.dumps(tool["input_schema"], indent=2)}\n"""\n')
