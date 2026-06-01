from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from redis.exceptions import RedisError as _RedisError
from sqlalchemy import select, update

from agent.node import get_node_type, registry
from config import USE_REDIS
from core.db import AsyncSessionLocal
from core.neo4j_client import get_driver
from core.redis_client import get_redis
from models.user import UserMemory

logger = logging.getLogger("canvas_graph")

_CANVAS_CACHE_TTL = 60

_WRITE_KEYWORDS = frozenset({"create", "delete", "set", "merge", "remove", "detach"})

# These live inside other nodes (insights=ghost card above Input; goals/automations=
# Config info section; mech=UNIT slot in Config) — never standalone canvas nodes.
_NON_CANVAS_TYPES = frozenset({"insights", "goals", "automations", "mech"})


# ── Redis cache helpers ──────────────────────────────────────────


def _cache_key(user_id: int) -> str:
    return f"canvas:{user_id}"


async def _cache_get(user_id: int) -> dict | None:
    if not USE_REDIS:
        return None
    try:
        r = get_redis()
        val = await r.get(_cache_key(user_id))
        if val:
            return json.loads(val)
    except _RedisError:
        pass
    return None


async def _cache_set(user_id: int, data: dict) -> None:
    if not USE_REDIS:
        return
    try:
        await get_redis().set(_cache_key(user_id), json.dumps(data), ex=_CANVAS_CACHE_TTL)
    except _RedisError:
        pass


async def _cache_del(user_id: int) -> None:
    if not USE_REDIS:
        return
    try:
        await get_redis().delete(_cache_key(user_id))
    except _RedisError:
        pass


# ── Node CRUD ────────────────────────────────────────────────────


async def create_node(user_id: int, node_type: str, config: dict | None = None) -> str:
    if node_type in _NON_CANVAS_TYPES:
        raise ValueError(
            f"'{node_type}' is not a standalone canvas node — it lives inside another node "
            f"(insights=Input ghost card; goals/automations/mech=Config). Do not create it."
        )
    node_def = get_node_type(node_type)
    if not node_def:
        raise ValueError(f"Unknown node type: {node_type}")

    merged = dict(node_def.default_config or {})
    if config:
        merged.update(config)

    node_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")

    async with driver.session() as session:
        result = await session.run(
            "CREATE (n:CanvasNode {"
            "  user_id: $uid,"
            "  node_id: $nid,"
            "  node_type: $type,"
            "  config: $config,"
            "  status: 'active',"
            "  created_at: $ts"
            "}) RETURN n.node_id",
            uid=user_id, nid=node_id, type=node_type,
            config=json.dumps(merged), ts=now,
        )
        await result.consume()

    await _cache_del(user_id)
    logger.info("[canvas] created node %s type=%s user=%d", node_id, node_type, user_id)
    return node_id


async def delete_node(user_id: int, node_id: str) -> None:
    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")

    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:CanvasNode {user_id: $uid, node_id: $nid}) "
            "OPTIONAL MATCH (n)-[r:WIRED_TO]-() "
            "DELETE r, n",
            uid=user_id, nid=node_id,
        )
        await result.consume()

    await _cache_del(user_id)
    logger.info("[canvas] deleted node %s user=%d", node_id, user_id)


async def update_node(
    user_id: int, node_id: str, config: dict | None = None, status: str | None = None
) -> None:
    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")

    sets = []
    params: dict = {"uid": user_id, "nid": node_id}

    if not config and not status:
        return

    async with driver.session() as session:
        if config is not None:
            # fetch current config JSON, merge in Python, write back
            read_r = await session.run(
                "MATCH (n:CanvasNode {user_id: $uid, node_id: $nid}) RETURN n.config AS cfg",
                uid=user_id, nid=node_id,
            )
            row = await read_r.single()
            if not row:
                raise ValueError(f"Node {node_id} not found")
            current = json.loads(row["cfg"] or "{}")
            current.update(config)
            params["config"] = json.dumps(current)
            sets.append("n.config = $config")

        if status is not None:
            sets.append("n.status = $status")
            params["status"] = status

        cypher = f"MATCH (n:CanvasNode {{user_id: $uid, node_id: $nid}}) SET {', '.join(sets)}"
        result = await session.run(cypher, **params)
        summary = await result.consume()
        if not summary.counters.contains_updates:
            raise ValueError(f"Node {node_id} not found")

    await _cache_del(user_id)
    logger.info("[canvas] updated node %s user=%d", node_id, user_id)


# ── Wiring ───────────────────────────────────────────────────────


async def find_wire(
    user_id: int, src_id: str, src_port: str, dst_id: str, dst_port: str
) -> dict | None:
    driver = get_driver()
    if not driver:
        return None

    async with driver.session() as session:
        result = await session.run(
            "MATCH (s:CanvasNode {user_id: $uid, node_id: $src_id}) "
            "MATCH (d:CanvasNode {user_id: $uid, node_id: $dst_id}) "
            "OPTIONAL MATCH (s)-[r:WIRED_TO {src_port: $sp, dst_port: $dp}]->(d) "
            "RETURN r IS NOT NULL AS exists, r.relation AS relation",
            uid=user_id, src_id=src_id, dst_id=dst_id, sp=src_port, dp=dst_port,
        )
        row = await result.single()
        if row and row["exists"]:
            return {
                "src_id": src_id, "dst_id": dst_id,
                "src_port": src_port, "dst_port": dst_port,
                "relation": row["relation"],
            }
    return None


async def wire_nodes(
    user_id: int, src_id: str, dst_id: str, src_port: str, dst_port: str, relation: str
) -> None:
    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")

    existing = await find_wire(user_id, src_id, src_port, dst_id, dst_port)
    if existing:
        raise ValueError(
            f"Wire already exists: {src_id}:{src_port} -> {dst_id}:{dst_port}"
        )

    async with driver.session() as session:
        node_result = await session.run(
            "MATCH (s:CanvasNode {user_id: $uid, node_id: $src_id}) RETURN s.node_type AS type",
            uid=user_id, src_id=src_id,
        )
        src_row = await node_result.single()
        if not src_row:
            raise ValueError(f"Source node {src_id} not found")
        src_type = src_row["type"]

        node_result = await session.run(
            "MATCH (d:CanvasNode {user_id: $uid, node_id: $dst_id}) RETURN d.node_type AS type",
            uid=user_id, dst_id=dst_id,
        )
        dst_row = await node_result.single()
        if not dst_row:
            raise ValueError(f"Destination node {dst_id} not found")
        dst_type = dst_row["type"]

    src_def = get_node_type(src_type)
    dst_def = get_node_type(dst_type)

    if not src_def or not dst_def:
        raise ValueError(f"Unknown node type in wire: src={src_type} dst={dst_type}")

    if src_port not in src_def.ports.get("output", []):
        raise ValueError(
            f"'{src_port}' is not an output port of {src_type} "
            f"(available outputs: {src_def.ports.get('output', [])})"
        )
    if dst_port not in dst_def.ports.get("input", []):
        raise ValueError(
            f"'{dst_port}' is not an input port of {dst_type} "
            f"(available inputs: {dst_def.ports.get('input', [])})"
        )

    async with driver.session() as session:
        result = await session.run(
            "MATCH (s:CanvasNode {user_id: $uid, node_id: $src_id}) "
            "MATCH (d:CanvasNode {user_id: $uid, node_id: $dst_id}) "
            "CREATE (s)-[:WIRED_TO {src_port: $sp, dst_port: $dp, relation: $rel}]->(d)",
            uid=user_id, src_id=src_id, dst_id=dst_id,
            sp=src_port, dp=dst_port, rel=relation,
        )
        await result.consume()

    await _cache_del(user_id)
    logger.info(
        "[canvas] wired %s:%s -> %s:%s user=%d",
        src_id, src_port, dst_id, dst_port, user_id,
    )


async def unwire_nodes(user_id: int, src_id: str, dst_id: str) -> None:
    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")

    async with driver.session() as session:
        result = await session.run(
            "MATCH (s:CanvasNode {user_id: $uid, node_id: $src_id}) "
            "-[r:WIRED_TO]->(d:CanvasNode {user_id: $uid, node_id: $dst_id}) "
            "DELETE r RETURN count(r) AS removed",
            uid=user_id, src_id=src_id, dst_id=dst_id,
        )
        row = await result.single()
        if row and row["removed"] == 0:
            raise ValueError(f"No wire found between {src_id} and {dst_id}")

    await _cache_del(user_id)
    logger.info("[canvas] unwired %s -> %s user=%d", src_id, dst_id, user_id)


# ── Query ────────────────────────────────────────────────────────


async def get_node(user_id: int, node_id: str) -> dict | None:
    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")

    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:CanvasNode {user_id: $uid, node_id: $nid}) "
            "OPTIONAL MATCH (n)-[w:WIRED_TO]->(c:CanvasNode {user_id: $uid}) "
            "OPTIONAL MATCH (p:CanvasNode {user_id: $uid})-[w2:WIRED_TO]->(n) "
            "RETURN n, "
            "  collect(DISTINCT {relation: w.relation, src_port: w.src_port, dst_port: w.dst_port, target_id: c.node_id}) AS outgoing, "
            "  collect(DISTINCT {relation: w2.relation, src_port: w2.src_port, dst_port: w2.dst_port, source_id: p.node_id}) AS incoming",
            uid=user_id, nid=node_id,
        )
        row = await result.single()
        if not row:
            return None

        node = dict(row["n"])
        cfg = node.get("config")
        node["config"] = json.loads(cfg) if isinstance(cfg, str) else (cfg or {})
        node["outgoing"] = [c for c in row["outgoing"] if c.get("target_id") is not None]
        node["incoming"] = [c for c in row["incoming"] if c.get("source_id") is not None]

        node_def = get_node_type(node.get("node_type", ""))
        if node_def:
            node["ports"] = node_def.ports
            node["available_tools"] = [t["name"] for t in node_def.tools]

        return node


async def get_canvas_graph(user_id: int) -> dict:
    cached = await _cache_get(user_id)
    if cached is not None:
        return cached

    driver = get_driver()
    if not driver:
        return {"nodes": [], "wires": []}

    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:CanvasNode {user_id: $uid}) "
            "OPTIONAL MATCH (n)-[w:WIRED_TO]->(c:CanvasNode {user_id: $uid}) "
            "RETURN n, collect({relation: w.relation, src_port: w.src_port, dst_port: w.dst_port, target_id: c.node_id}) AS connections",
            uid=user_id,
        )
        rows = await result.data()

    nodes = []
    wires = []
    seen_wires: set[tuple[str, str]] = set()

    for row in rows:
        node_data = dict(row["n"])
        cfg = node_data.get("config")
        node_data["config"] = json.loads(cfg) if isinstance(cfg, str) else (cfg or {})
        node_def = get_node_type(node_data.get("node_type", ""))
        if node_def:
            node_data["ports"] = node_def.ports

        conns = [c for c in row["connections"] if c.get("target_id") is not None]
        node_data["connections"] = [
            {
                "target_id": c["target_id"],
                "relation": c["relation"],
                "src_port": c.get("src_port"),
                "dst_port": c.get("dst_port"),
            }
            for c in conns
        ]

        for c in conns:
            wire_key = (node_data["node_id"], c["target_id"])
            if wire_key not in seen_wires:
                seen_wires.add(wire_key)
                wires.append({
                    "src_id": node_data["node_id"],
                    "dst_id": c["target_id"],
                    "relation": c["relation"],
                    "src_port": c.get("src_port"),
                    "dst_port": c.get("dst_port"),
                })

        nodes.append(node_data)

    result_data = {"nodes": nodes, "wires": wires}
    await _cache_set(user_id, result_data)
    return result_data


async def find_nodes(user_id: int, node_type: str) -> list[dict]:
    driver = get_driver()
    if not driver:
        return []

    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:CanvasNode {user_id: $uid, node_type: $type}) RETURN n",
            uid=user_id, type=node_type,
        )
        rows = await result.data()

    nodes = []
    for row in rows:
        n = dict(row["n"])
        cfg = n.get("config")
        n["config"] = json.loads(cfg) if isinstance(cfg, str) else (cfg or {})
        nodes.append(n)
    return nodes


async def query_canvas(
    user_id: int, cypher: str, params: dict | None = None
) -> list[dict]:
    first_word = cypher.lstrip().split(maxsplit=1)[0].upper() if cypher.strip() else ""
    if first_word in _WRITE_KEYWORDS:
        raise ValueError(f"Write operation '{first_word}' not allowed in query_canvas")

    if "$uid" not in cypher:
        raise ValueError("Cypher query must include {user_id: $uid} to scope to current user")

    if ":CanvasNode" not in cypher:
        raise ValueError("Cypher query must scope to :CanvasNode nodes (e.g. MATCH (n:CanvasNode {user_id: $uid}))")

    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")

    query_params = dict(params or {})
    query_params["uid"] = user_id

    async with driver.session() as session:
        result = await session.run(cypher, **query_params)
        return await result.data()


# ── Scratchpad ───────────────────────────────────────────────────


async def get_scratchpad(user_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserMemory.agent_scratchpad).where(UserMemory.user_id == user_id)
        )
        val = result.scalar()
        return val or {}


async def update_scratchpad(user_id: int, scratchpad: dict) -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(UserMemory.agent_scratchpad).where(UserMemory.user_id == user_id)
        )
        current = existing.scalar() or {}
        merged = {**current, **scratchpad}
        await db.execute(
            update(UserMemory)
            .where(UserMemory.user_id == user_id)
            .values(agent_scratchpad=merged)
        )
        await db.commit()
