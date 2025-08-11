from typing import TypeVar
K = TypeVar('K')
V = TypeVar('V')

def lastkey(data: dict[K, V], *default: K) -> K:
    if not data and not default:
        raise IndexError("key index out of range")
    return list(data.keys())[-1] if data else default[0]

def lastvalue(data: dict[K, V], *default: V) -> V:
    if not data and not default:
        raise IndexError("value index out of range")
    return data[list(data.keys())[-1]] if data else default[0]

def lastitem(data: dict[K, V], *default: tuple[K, V]) -> tuple[K, V]:
    if not data and not default:
        raise IndexError("item index out of range")
    return (list(data.keys())[-1], data[list(data.keys())[-1]]) if data else default[0]
