import json
from pathlib import Path

CONFIG_DIR = Path('~/.ask/').expanduser()
CONFIG_PATH = CONFIG_DIR / 'ask.json'

class Config:
    def __init__(self):
        self.data = {}
        CONFIG_DIR.mkdir(parents=False, exist_ok=True)
        if CONFIG_PATH.is_file():
            self.data = json.loads(CONFIG_PATH.read_text() or '{}')
        if not self.data:
            self.data = {'history': []}

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)
