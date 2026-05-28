import math
from datetime import datetime, timezone

_SALIENCE_DECAY = 0.95


def compute_salience(
    base_salience: float,
    access_count: int = 0,
    age_days: float = 0.0,
    emphasis: float = 1.0,
) -> float:
    access_boost = 1.0 + min(access_count, 10) * 0.1
    age_decay = math.exp(-0.05 * age_days)
    raw = base_salience * access_boost * age_decay * emphasis
    return round(min(max(raw, 0.0), 2.0), 4)


def decay_salience(salience: float, cycles: int = 1) -> float:
    for _ in range(cycles):
        salience *= _SALIENCE_DECAY
    return round(max(salience, 0.0), 4)
