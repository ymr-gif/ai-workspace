import json
import logging
from datetime import datetime, timezone
from itertools import combinations

from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from llm.nim import call
from models import MemoryConflict, UserMemory

logger = logging.getLogger("summarizer")

_MODEL = MODELS["llama"]

_SYSTEM = (
    "You are a fact conflict detector. "
    "Given two facts, respond with JSON only: "
    '{\"conflict_type\": \"contradiction\"|\"duplicate\"|\"ambiguous\"|\"none\"}'
)


async def detect_conflicts(content: str) -> list[dict]:
    facts = [line.strip() for line in content.split("\n") if line.strip()]
    if len(facts) < 2:
        return []

    results = []
    for fact_a, fact_b in combinations(facts, 2):
        prompt = f'Fact A: {fact_a}\nFact B: {fact_b}'
        resp = await call(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            request_id="conflict-detect",
        )
        if not resp.get("ok"):
            continue
        raw = (resp.get("content") or "").strip()
        try:
            data = json.loads(raw)
            ct = data.get("conflict_type", "none")
        except Exception:
            ct = "none"
        if ct != "none":
            results.append({"fact_a": fact_a, "fact_b": fact_b, "conflict_type": ct})

    return results


async def resolve_conflict(conflict: MemoryConflict, strategy: str, db: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    conflict.resolution  = strategy
    conflict.resolved_at = now

    if strategy in ("keep_a", "keep_b", "merge", "discard_both"):
        mem = await db.get(UserMemory, conflict.user_id)
        if not mem:
            return

        lines = [l for l in mem.content.split("\n") if l.strip()]

        if strategy == "keep_a":
            lines = [l for l in lines if l.strip() != conflict.fact_b]
        elif strategy == "keep_b":
            lines = [l for l in lines if l.strip() != conflict.fact_a]
        elif strategy == "discard_both":
            lines = [l for l in lines if l.strip() not in (conflict.fact_a, conflict.fact_b)]
        elif strategy == "merge":
            lines = [l for l in lines if l.strip() not in (conflict.fact_a, conflict.fact_b)]
            lines.append(f"{conflict.fact_a} / {conflict.fact_b}")

        mem.content  = "\n".join(lines)
        mem.version += 1
        mem.updated_at = now
