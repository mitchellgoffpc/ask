import os
import tomllib
from pathlib import Path
from typing import cast
from datetime import date

def is_git_repo() -> bool:
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / '.git').exists():
            return True
        current = current.parent
    return False

def load_system_prompt() -> str:
    prompt_file = Path(__file__).parent / "system.toml"
    with open(prompt_file, "rb") as f:
        prompt = cast(str, tomllib.load(f)['prompt'])
    return prompt.format(
        working_directory=Path.cwd().resolve(),
        is_git_repo="Yes" if is_git_repo() else "No",
        platform=os.uname().sysname,
        os_version=f"{os.uname().sysname.lower()} {os.uname().release}",
        current_date=date.today().strftime('%Y-%m-%d'),
    )

def load_tool_prompt(tool_name: str) -> str:
    prompt_file = Path(__file__).parent / "tools" / f"{tool_name}.toml"
    if not prompt_file.is_file():
        raise FileNotFoundError(f"Tool prompt file for '{tool_name}' not found.")
    with open(prompt_file, "rb") as f:
        data = tomllib.load(f)
    return cast(str, data['prompt']).strip()
