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


def score_facts(content: str, fact_saliences: dict) -> list[tuple[str, float]]:
    lines = [l for l in content.split("\n") if l.strip()]
    scored = []
    for l in lines:
        score = fact_saliences.get(l.strip(), 1.0)
        scored.append((l, score))
    scored.sort(key=lambda x: -x[1])
    return scored


def bump_fact_saliences(facts: list[str], fact_saliences: dict) -> dict:
    result = dict(fact_saliences)
    for f in facts:
        key = f.strip()
        if not key:
            continue
        current = result.get(key, 1.0)
        result[key] = compute_salience(current, access_count=1)
    return result


def decay_fact_saliences(fact_saliences: dict) -> dict:
    result = {}
    for key, val in fact_saliences.items():
        d = decay_salience(val)
        if d >= 0.05:
            result[key] = d
    return result
