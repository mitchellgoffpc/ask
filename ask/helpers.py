from typing import TypeVar
K = TypeVar('K')
V = TypeVar('V')

def lastkey(data: dict[K, V], default: K | None = None) -> K | None:
    keys = list(data.keys())
    return keys[-1] if keys else default

def lastvalue(data: dict[K, V], default: V | None = None) -> V | None:
    keys = list(data.keys())
    return data[keys[-1]] if keys else default

def lastitem(data: dict[K, V]) -> tuple[K, V]:
    keys = list(data.keys())
    return keys[-1], data[keys[-1]]
