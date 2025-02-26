from dataclasses import dataclass

@dataclass
class Tool:
    name: str
    description: str

    def execute(self, *args, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")
