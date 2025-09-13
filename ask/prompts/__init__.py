import os
import tomllib
from datetime import date
from functools import cache
from pathlib import Path

def get_relative_path(path: Path | str) -> str:
    try:
        return str(Path(path).relative_to(Path.cwd()))
    except ValueError:
        return str(path)

def is_git_repo() -> bool:
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / '.git').exists():
            return True
        current = current.parent
    return False

@cache
def load_prompt_file(prompt_file: str) -> dict[str, str]:
    prompt_path = Path(__file__).parent / prompt_file
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Prompt file '{prompt_path}' not found.")
    with open(prompt_path, "rb") as f:
        return tomllib.load(f)

def load_system_prompt() -> str:
    return load_prompt_file('system.toml')['prompt'].format(
        working_directory=Path.cwd().resolve(),
        is_git_repo="Yes" if is_git_repo() else "No",
        platform=os.uname().sysname,
        os_version=f"{os.uname().sysname.lower()} {os.uname().release}",
        current_date=date.today().strftime('%Y-%m-%d'))

def load_tool_prompt(tool_name: str, key: str = "prompt") -> str:
    return load_prompt_file(f'tools/{tool_name}.toml')[key].strip()
