import time
from collections import OrderedDict
from typing import Optional

_MAX_SIZE = 1000

_store:  OrderedDict[str, dict]  = OrderedDict()
_expiry: dict[str, float]        = {}


def get(key: str) -> Optional[dict]:
    expires = _expiry.get(key)
    if expires and time.time() > expires:
        _store.pop(key, None)
        _expiry.pop(key, None)
        return None
    return _store.get(key)


def set(key: str, payload: dict, ttl: int) -> None:
    _store[key]  = payload
    _expiry[key] = time.time() + ttl
    _store.move_to_end(key)
    if len(_store) > _MAX_SIZE:
        oldest, _ = _store.popitem(last=False)
        _expiry.pop(oldest, None)


def size() -> int:
    return len(_store)
