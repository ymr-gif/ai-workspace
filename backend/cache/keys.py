import hashlib

CACHE_VERSION = "v3"


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def make_key(
    message: str,
    *,
    model: str = "",
    history_tail: str = "",
    system_prompt: str = "",
) -> str:
    raw = (
        f"{CACHE_VERSION}:{normalize(message)}"
        f"|m:{model}"
        f"|h:{normalize(history_tail)}"
        f"|s:{normalize(system_prompt)}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()
