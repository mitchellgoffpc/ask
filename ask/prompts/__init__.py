import tomllib
from pathlib import Path
from typing import cast

def load_system_prompt() -> str:
    prompt_file = Path(__file__).parent / "system.toml"
    with open(prompt_file, "rb") as f:
        data = tomllib.load(f)
    return cast(str, data["prompt"])

def load_tool_prompt(tool_name: str) -> str:
    prompt_file = Path(__file__).parent / "tools" / f"{tool_name}.toml"
    if not prompt_file.is_file():
        raise FileNotFoundError(f"Tool prompt file for '{tool_name}' not found.")
    with open(prompt_file, "rb") as f:
        data = tomllib.load(f)
    return cast(str, data['prompt'])
