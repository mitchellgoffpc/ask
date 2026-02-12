import json
import sys
from pathlib import Path

PROMPT_DIR = Path(__file__).parent

if __name__ == '__main__':
    with Path(sys.argv[1]).open() as f:
        data = json.load(f)

    with (PROMPT_DIR / "system.toml").open("w") as f:
        f.write('prompt = """\n')
        f.write(data['instructions'].strip().replace('\\', '\\\\'))
        f.write('\n"""\n')

    with (PROMPT_DIR / "permissions.toml").open("w") as f:
        f.write('prompt = """\n')
        f.write(data['input'][0]['content'][0]['text'].strip().replace(' \n', '\n'))
        f.write('\n"""\n')

    (PROMPT_DIR / 'tools').mkdir(exist_ok=True)
    for tool in data['tools']:
        if 'name' not in tool:
            continue
        with (PROMPT_DIR / 'tools' / f"{tool['name']}.toml").open("w") as f:
            f.write(f'name = "{tool["name"]}"\n')
            f.write(f'description = """\n{tool["description"].strip()}\n"""\n\n')
            if 'parameters' in tool:
                f.write(f'parameters = """\n{json.dumps(tool["parameters"], indent=2)}\n"""\n')
            elif 'format' in tool:
                f.write(f'schema = """\n{tool["format"]["definition"].strip()}\n"""\n')
            else:
                raise Exception
