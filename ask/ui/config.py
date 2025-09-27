import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path('~/.ask/').expanduser()
CONFIG_PATH = CONFIG_DIR / 'config.json'
HISTORY_PATH = CONFIG_DIR / 'history.json'
DEFAULT_CONFIG = {'editor': 'vim', 'default_model': 'sonnet'}

class History:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=False, exist_ok=True)
        self.data: list[str] = json.loads(HISTORY_PATH.read_text() or '[]') if HISTORY_PATH.is_file() else []

    def __iter__(self):
        return iter(self.data)

    def append(self, item: str) -> None:
        self.data.append(item)
        with open(HISTORY_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

class Config:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=False, exist_ok=True)
        self.data: dict[str, Any] = DEFAULT_CONFIG | (json.loads(CONFIG_PATH.read_text() or '{}') if CONFIG_PATH.is_file() else {})

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)
