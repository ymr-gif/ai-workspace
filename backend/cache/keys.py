import hashlib

CACHE_VERSION = "v1"


def normalize(message: str) -> str:
    return " ".join(message.lower().strip().split())


def make_key(message: str) -> str:
    raw = f"{CACHE_VERSION}:{normalize(message)}"
    return hashlib.sha256(raw.encode()).hexdigest()
