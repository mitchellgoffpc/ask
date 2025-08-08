from typing import TypeVar
K = TypeVar('K')
V = TypeVar('V')

def lastkey(data: dict[K, V]) -> K:
    return list(data.keys())[-1]

def lastvalue(data: dict[K, V]) -> V:
    return data[lastkey(data)]

def lastitem(data: dict[K, V]) -> tuple[K, V]:
    key = lastkey(data)
    return key, data[key]
