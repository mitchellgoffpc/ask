import json
from pathlib import Path
from typing import Any, Iterator

CONFIG_DIR = Path('~/.ask/').expanduser()
CONFIG_PATH = CONFIG_DIR / 'config.json'
HISTORY_PATH = CONFIG_DIR / 'history.json'
DEFAULT_CONFIG = {'editor': 'vim', 'default_model': 'sonnet'}

class _History:
    _data: list[str] | None = None

    @property
    def data(self) -> list[str]:
        if self._data is None:
            CONFIG_DIR.mkdir(parents=False, exist_ok=True)
            self._data = json.loads(HISTORY_PATH.read_text() or '[]') if HISTORY_PATH.is_file() else []
        return self._data

    def __iter__(self) -> Iterator[str]:
        return iter(self.data)

    def append(self, item: str) -> None:
        self.data.append(item)
        with open(HISTORY_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

class _Config:
    _data: dict[str, Any] | None = None

    @property
    def data(self) -> dict[str, Any]:
        if self._data is None:
            CONFIG_DIR.mkdir(parents=False, exist_ok=True)
            self._data = DEFAULT_CONFIG | (json.loads(CONFIG_PATH.read_text() or '{}') if CONFIG_PATH.is_file() else {})
        return self._data

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

Config = _Config()
History = _History()
