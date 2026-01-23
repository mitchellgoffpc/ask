import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path('~/.ask/').expanduser()
CONFIG_PATH = CONFIG_DIR / 'config.json'
HISTORY_PATH = CONFIG_DIR / 'history.json'
DEFAULT_CONFIG: dict[str, Any] = {'editor': 'vim', 'default_model': 'sonnet'}
DEFAULT_HISTORY: dict[str, Any] = {'queries': []}

class BaseConfig:
    _path: Path
    _default: dict[str, Any]
    _data: dict[str, Any] | None = None

    def __init__(self, path: Path, default: dict[str, Any]) -> None:
        self._path = path
        self._default = default

    @property
    def data(self) -> dict[str, Any]:
        if self._data is None:
            self._path.parent.mkdir(parents=False, exist_ok=True)
            self._data = self._default | (json.loads(self._path.read_text() or '{}') if self._path.is_file() else {})
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)

Config = BaseConfig(CONFIG_PATH, DEFAULT_CONFIG)
History = BaseConfig(HISTORY_PATH, DEFAULT_HISTORY)
