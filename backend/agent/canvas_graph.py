from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone

from redis.exceptions import RedisError as _RedisError

from agent.node import (
    EMBEDDED_TYPES,
    MANAGED_TYPES,
    PERMANENT_TYPES,
    get_node_type,
)
from config import USE_REDIS
from core.neo4j_client import get_driver
from core.redis_client import get_redis

logger = logging.getLogger("canvas_graph")

_CANVAS_CACHE_TTL = 60

_WRITE_KEYWORDS = frozenset({"create", "delete", "set", "merge", "remove", "detach"})
# Reject any write clause anywhere in the query (not just the first word) so a
# read-only query_canvas can't smuggle a mutation, e.g. `MATCH (...) DELETE n`.
# Case-insensitive + word-boundaried (won't trip on n.created_at / 'settings').
_WRITE_RE = re.compile(r"\b(" + "|".join(sorted(_WRITE_KEYWORDS)) + r")\b", re.I)

# Auto-scope the common omission: a bare `(var:CanvasNode)` node pattern with no
# property map. The 70B frequently forgets the `{user_id: $uid}` filter; inject
# it into EVERY such pattern (no count limit — a multi-binding query must not
# leave a second binding unscoped).
_BARE_CANVAS_NODE_RE = re.compile(r"\(\s*(\w*)\s*:CanvasNode\s*\)")

# After auto-scoping, every `:CanvasNode` binding MUST be filtered by
# `{user_id: $uid}` (extra props allowed after it). This matches a `:CanvasNode`
# NOT immediately followed by that scoped map — i.e. an unscoped repeat, a
# multi-label node, or a literal cross-user filter like `{user_id: 999}`. Its
# presence ⇒ reject the query, preventing cross-tenant reads via query_canvas.
# (`\s*` lives inside the lookahead so greedy backtracking can't false-pass.)
_UNSCOPED_CANVAS_RE = re.compile(r":CanvasNode(?!\s*\{\s*user_id:\s*\$uid\b)")


# ── helpers ───────────────────────────────────────────────────────


def _ensure_driver():
    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")
    return driver


def _deserialize_node(row_data: dict) -> dict:
    node = dict(row_data)
    cfg = node.get("config")
    node["config"] = json.loads(cfg) if isinstance(cfg, str) else (cfg or {})
    node_def = get_node_type(node.get("node_type", ""))
    if node_def:
        node["ports"] = node_def.ports
    return node


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


async def _find_duplicate(user_id: int, node_type: str, config: dict) -> str | None:
    if node_type in PERMANENT_TYPES:
        existing = await find_nodes(user_id, node_type)
        if not existing:
            return None
        protected = next((n for n in existing if n.get("protected")), None)
        return (protected or existing[0])["node_id"]

    key = "conversation_id" if node_type == "session" else None
    if key and config.get(key):
        for n in await find_nodes(user_id, node_type):
            if (n.get("config") or {}).get(key) == config[key]:
                return n["node_id"]
    return None


async def create_node(
    user_id: int, node_type: str, config: dict | None = None, internal: bool = False
) -> str:
    if node_type in EMBEDDED_TYPES:
        raise ValueError(
            f"'{node_type}' is not a standalone canvas node — it lives inside another node "
            f"(insights=Input ghost card; goals/automations/mech=Config). Do not create it."
        )
    if node_type in MANAGED_TYPES and not internal:
        raise ValueError(
            f"'{node_type}' is managed automatically — do not create it directly. "
            f"input, memory and config already exist; create sessions via create_conversation."
        )
    node_def = get_node_type(node_type)
    if not node_def:
        raise ValueError(f"Unknown node type: {node_type}")

    if config and config.get("conversation_id") is not None:
        try:
            uuid.UUID(str(config["conversation_id"]))
        except (ValueError, TypeError, AttributeError):
            raise ValueError(
                f"Invalid conversation_id {config['conversation_id']!r}: must be a real "
                f"conversation UUID. Create the conversation first, then reference its id."
            )

    merged = dict(node_def.default_config or {})
    if config:
        merged.update(config)

    dup_id = await _find_duplicate(user_id, node_type, merged)
    if dup_id:
        logger.info("[canvas] dedup: %s already exists as %s user=%d", node_type, dup_id, user_id)
        return dup_id

    node_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    driver = _ensure_driver()
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
    driver = _ensure_driver()
    async with driver.session() as session:
        chk = await session.run(
            "MATCH (n:CanvasNode {user_id: $uid, node_id: $nid}) "
            "RETURN coalesce(n.protected, false) AS protected",
            uid=user_id, nid=node_id,
        )
        row = await chk.single()
        if row is None:
            raise ValueError(f"Node {node_id} not found")
        if row["protected"]:
            raise ValueError(
                f"Cannot delete core node {node_id}: the input node and the global "
                f"JARVIS session are permanent infrastructure."
            )

        result = await session.run(
            "MATCH (n:CanvasNode {user_id: $uid, node_id: $nid}) "
            "OPTIONAL MATCH (n)-[r:WIRED_TO]-() "
            "DELETE r, n",
            uid=user_id, nid=node_id,
        )
        summary = await result.consume()
        if summary.counters.nodes_deleted == 0:
            raise ValueError(f"Node {node_id} not found")

    await _cache_del(user_id)
    logger.info("[canvas] deleted node %s user=%d", node_id, user_id)


async def set_protected(user_id: int, node_id: str, value: bool = True) -> None:
    driver = get_driver()
    if not driver:
        return
    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:CanvasNode {user_id: $uid, node_id: $nid}) SET n.protected = $v",
            uid=user_id, nid=node_id, v=value,
        )
        await result.consume()
    await _cache_del(user_id)


async def update_node(
    user_id: int, node_id: str, config: dict | None = None, status: str | None = None
) -> None:
    if not config and not status:
        return

    driver = _ensure_driver()
    sets = []
    params: dict = {"uid": user_id, "nid": node_id}

    async with driver.session() as session:
        if config is not None:
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
    driver = _ensure_driver()

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
    driver = _ensure_driver()
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
    driver = _ensure_driver()
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

        node = _deserialize_node(row["n"])
        node["outgoing"] = [c for c in row["outgoing"] if c.get("target_id") is not None]
        node["incoming"] = [c for c in row["incoming"] if c.get("source_id") is not None]

        node_def = get_node_type(node.get("node_type", ""))
        if node_def:
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
        node_data = _deserialize_node(row["n"])

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
            "MATCH (n:CanvasNode {user_id: $uid, node_type: $type}) "
            "RETURN n ORDER BY n.created_at, n.node_id",
            uid=user_id, type=node_type,
        )
        rows = await result.data()

    return [_deserialize_node(row["n"]) for row in rows]


# ── Raw query (read-only) ────────────────────────────────────────


async def query_canvas(
    user_id: int, cypher: str, params: dict | None = None
) -> list[dict]:
    _wm = _WRITE_RE.search(cypher)
    if _wm:
        raise ValueError(f"Write operation '{_wm.group(1).upper()}' not allowed in query_canvas (read-only)")

    if ":CanvasNode" not in cypher:
        raise ValueError("Cypher query must scope to :CanvasNode nodes (e.g. MATCH (n:CanvasNode {user_id: $uid}))")

    # Auto-scope EVERY bare (var:CanvasNode) pattern with {user_id: $uid} — no
    # count limit, so a multi-binding query can't leave a second binding open.
    scoped = _BARE_CANVAS_NODE_RE.sub(r"(\1:CanvasNode {user_id: $uid})", cypher)
    if scoped != cypher:
        logger.info("[canvas] query_canvas auto-scoped user=%d", user_id)
        cypher = scoped

    # Enforce per-tenant scoping on EVERY :CanvasNode binding. Rejects unscoped
    # repeats, multi-label nodes, and literal cross-user filters ({user_id: 999})
    # — the substitution alone is not sufficient (it can't fix a non-bare
    # pattern). This is the actual cross-tenant guard; scoping the node pattern
    # is authoritative (a later WHERE cannot widen it).
    if _UNSCOPED_CANVAS_RE.search(cypher):
        raise ValueError(
            "Every (:CanvasNode) pattern must be scoped with {user_id: $uid}. "
            "Use a bare MATCH (n:CanvasNode) RETURN n (auto-scoped) or write "
            "{user_id: $uid} explicitly. Cross-user filters are not allowed."
        )

    driver = get_driver()
    if not driver:
        raise RuntimeError("Neo4j driver not available")

    query_params = dict(params or {})
    query_params["uid"] = user_id

    async with driver.session() as session:
        result = await session.run(cypher, **query_params)
        return await result.data()
