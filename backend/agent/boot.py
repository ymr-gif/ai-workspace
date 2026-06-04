from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import text

import llm.client as llm_client
from config import MODELS, MODEL_EMBEDDING, NVIDIA_API_KEY, NIM_URL, NIM_EMBEDDING_URL
from core.db import AsyncSessionLocal
from core.neo4j_client import get_health as neo4j_health
from core.redis_client import get_redis

from agent.canvas_graph import get_canvas_graph
from agent.scratchpad import get_scratchpad

logger = logging.getLogger("boot")

_PING_TIMEOUT = 5


@dataclass
class BootReport:
    health: dict[str, bool] = field(default_factory=dict)
    scratchpad: dict = field(default_factory=dict)
    canvas: dict = field(default_factory=dict)
    node_summary: str = ""


async def _ping_model(role: str, model_id: str) -> bool:
    try:
        resp = await llm_client.client.post(
            NIM_URL,
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=_PING_TIMEOUT,
        )
        return resp.status_code == 200
    except Exception:
        return False


async def _ping_embedding() -> bool:
    try:
        resp = await llm_client.client.post(
            NIM_EMBEDDING_URL,
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL_EMBEDDING, "input": ["ping"], "input_type": "passage", "encoding_format": "float"},
            timeout=_PING_TIMEOUT,
        )
        return resp.status_code == 200
    except Exception:
        return False


async def _ping_neo4j() -> bool:
    try:
        h = await neo4j_health()
        return h.get("available", False)
    except Exception:
        return False


async def _ping_redis() -> bool:
    try:
        r = get_redis()
        await asyncio.wait_for(r.ping(), timeout=3)
        return True
    except Exception:
        return False


async def _ping_db() -> bool:
    try:
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2)
        return True
    except Exception:
        return False


async def _check_health() -> dict[str, bool]:
    model_tasks = [_ping_model(role, mid) for role, mid in MODELS.items()]
    model_tasks.append(_ping_embedding())
    results = await asyncio.gather(*model_tasks, return_exceptions=True)

    health: dict[str, bool] = {}
    for i, (role, _) in enumerate(MODELS.items()):
        health[role] = bool(results[i]) if not isinstance(results[i], Exception) else False
    health["embedding"] = bool(results[len(MODELS)]) if not isinstance(results[len(MODELS)], Exception) else False

    svc_tasks = await asyncio.gather(
        _ping_neo4j(), _ping_redis(), _ping_db(), return_exceptions=True,
    )
    health["neo4j"] = bool(svc_tasks[0]) if not isinstance(svc_tasks[0], Exception) else False
    health["redis"] = bool(svc_tasks[1]) if not isinstance(svc_tasks[1], Exception) else False
    health["db"] = bool(svc_tasks[2]) if not isinstance(svc_tasks[2], Exception) else False

    return health


async def agent_boot(user_id: int) -> BootReport:
    health = await _check_health()
    scratchpad = await get_scratchpad(user_id)
    canvas = await get_canvas_graph(user_id)

    nodes = canvas.get("nodes", [])
    node_count = len(nodes)
    wire_count = sum(len(n.get("connections", [])) for n in nodes)

    return BootReport(
        health=health,
        scratchpad=scratchpad,
        canvas=canvas,
        node_summary=f"{node_count} active nodes, {wire_count} connections",
    )


def format_boot_log(report: BootReport) -> str:
    lines = ["=== AGENT BOOT LOG ==="]
    for model, ok in report.health.items():
        lines.append(f"> {model.upper()} ... {'OK' if ok else 'FAIL'}")
    lines.append(f"> CANVAS: {report.node_summary}")
    if report.scratchpad:
        lines.append(f"> LAST CONTEXT: {report.scratchpad.get('summary', 'restored')}")
    lines.append("=== STANDBY ===")
    return "\n".join(lines)
