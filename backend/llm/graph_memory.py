import hashlib
import json
import logging
from datetime import datetime, timezone

from redis.exceptions import RedisError

from config import MODELS, USE_REDIS
from core.neo4j_client import get_driver
from core.redis_client import get_redis

_GRAPH_CACHE_TTL       = 60    # seconds
_MAX_ENTITY_NAME_LEN   = 200
_MAX_ENTITIES_PER_CALL = 30
_MAX_RELS_PER_CALL     = 60
_MAX_USER_ENTITIES     = 500


def _cache_key(user_id: int, query_text: str) -> str:
    digest = hashlib.sha256(query_text.lower().strip().encode()).hexdigest()[:32]
    return f"graph:{user_id}:{digest}"


async def _cache_get(key: str) -> str | None:
    if not USE_REDIS:
        return None
    try:
        return await get_redis().get(key)
    except RedisError:
        return None


async def _cache_set(key: str, value: str) -> None:
    if not USE_REDIS:
        return
    try:
        await get_redis().set(key, value, ex=_GRAPH_CACHE_TTL)
    except RedisError:
        pass


async def _cache_del_user(user_id: int) -> None:
    if not USE_REDIS:
        return
    try:
        r = get_redis()
        keys = [k async for k in r.scan_iter(f"graph:{user_id}:*")]
        if keys:
            await r.delete(*keys)
    except RedisError:
        pass

logger = logging.getLogger("graph_memory")

_STOPWORDS = frozenset({
    "the", "this", "that", "and", "for", "are", "was", "has", "had",
    "but", "not", "with", "from", "they", "you", "its", "all", "can",
    "just", "about", "been", "what", "when", "where", "who", "how",
    "which", "will", "would", "could", "should", "does", "into", "than",
})

_EXTRACT_PROMPT = (
    "Extract entities and relationships from this conversation exchange.\n"
    "Return ONLY valid JSON:\n"
    '{{"entities": [{{"name": "...", "type": "PERSON|PLACE|CONCEPT|TECHNOLOGY|ORGANIZATION|EVENT|OTHER"}}],'
    ' "relations": [{{"from": "entity_name", "to": "entity_name", "type": "USES|KNOWS|RELATED_TO|CREATED|WORKS_AT|..."}}]}}\n\n'
    "User: {message}\nAssistant: {response}\n\nJSON only:"
)


async def extract_and_store(user_id: int, message: str, response: str) -> None:
    driver = get_driver()
    if not driver:
        return

    from llm.nim import call

    prompt = _EXTRACT_PROMPT.format(message=message[:500], response=response[:800])

    try:
        result = await call(
            model=MODELS["reasoning"],
            messages=[{"role": "user", "content": prompt}],
            request_id=f"graph-{user_id}",
        )
        raw = (result.get("content") or "").strip()

        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]

        data      = json.loads(raw)
        entities  = data.get("entities", [])
        relations = data.get("relations", [])

        if not entities:
            return

        now = datetime.now(timezone.utc).isoformat()

        entity_batch = [
            {"name": (e.get("name") or "").strip(), "type": (e.get("type") or "OTHER").strip()}
            for e in entities
            if (e.get("name") or "").strip()
            and len((e.get("name") or "").strip()) <= _MAX_ENTITY_NAME_LEN
        ]

        entity_batch = entity_batch[:_MAX_ENTITIES_PER_CALL]

        valid_names = {e["name"] for e in entity_batch}
        rel_batch = [
            {
                "src":   (r.get("from") or "").strip(),
                "dst":   (r.get("to")   or "").strip(),
                "rtype": (r.get("type") or "RELATED_TO").strip().upper().replace(" ", "_"),
            }
            for r in relations
            if (r.get("from") or "").strip() in valid_names
            and (r.get("to") or "").strip() in valid_names
        ][:_MAX_RELS_PER_CALL]

        if USE_REDIS:
            try:
                if await get_redis().exists(f"compact:running:{user_id}"):
                    logger.info("[graph] skipping extract — compaction running user=%d", user_id)
                    return
            except RedisError:
                pass

        async with driver.session() as session:
            if entity_batch:
                cnt_result = await session.run(
                    "MATCH (n:Entity {user_id: $uid}) RETURN count(n) AS cnt",
                    uid=user_id,
                )
                record = await cnt_result.single()
                current_count = record["cnt"] if record else 0
                overflow = current_count + len(entity_batch) - _MAX_USER_ENTITIES
                if overflow > 0:
                    logger.info("[graph] evicting %d oldest entities user=%d", overflow, user_id)
                    await session.run(
                        "MATCH (n:Entity {user_id: $uid}) "
                        "WITH n ORDER BY n.updated_at ASC LIMIT $n "
                        "DETACH DELETE n",
                        uid=user_id, n=overflow,
                    )
                await session.run(
                    "UNWIND $batch AS e "
                    "MERGE (n:Entity {user_id: $uid, name: e.name}) "
                    "SET n.type = CASE WHEN e.type <> 'OTHER' THEN e.type ELSE n.type END, "
                    "    n.updated_at = $ts",
                    batch=entity_batch, uid=user_id, ts=now,
                )
                await _cache_del_user(user_id)

            if rel_batch:
                await session.run(
                    "UNWIND $batch AS r "
                    "MATCH (a:Entity {user_id: $uid, name: r.src}), "
                    "      (b:Entity {user_id: $uid, name: r.dst}) "
                    "MERGE (a)-[rel:RELATED_TO {type: r.rtype}]->(b) "
                    "SET rel.updated_at = $ts",
                    batch=rel_batch, uid=user_id, ts=now,
                )

        logger.info("[graph] stored %d entities %d rels user=%d", len(entity_batch), len(rel_batch), user_id)

    except json.JSONDecodeError:
        logger.debug("[graph] LLM returned non-JSON, skipping")
    except Exception:
        logger.exception("[graph] extract_and_store failed user=%d", user_id)


async def merge_duplicate_entities(user_id: int) -> int:
    import re
    driver = get_driver()
    if not driver:
        return 0

    def _norm(name: str) -> str:
        n = name.lower().strip()
        n = re.sub(r'\s+', ' ', n)
        n = n.rstrip('s')
        return n

    async with driver.session() as session:
        result = await session.run(
            "MATCH (e:Entity {user_id: $uid}) RETURN e.name AS name, e.type AS type",
            uid=user_id,
        )
        rows = await result.data()

    if not rows:
        return 0

    groups: dict[str, list[dict]] = {}
    for row in rows:
        key = _norm(row["name"])
        groups.setdefault(key, []).append(row)

    merged = 0
    for key, group in groups.items():
        if len(group) < 2:
            continue

        names = sorted((g["name"] for g in group), key=len, reverse=True)
        keep_name = names[0]

        keep_type = "OTHER"
        for g in group:
            t = g.get("type", "OTHER")
            if t != "OTHER":
                keep_type = t

        to_delete = [g["name"] for g in group if g["name"] != keep_name]
        if not to_delete:
            continue

        ts = datetime.now(timezone.utc).isoformat()
        async with driver.session() as session:
            await session.run(
                "MATCH (n:Entity {user_id: $uid, name: $name}) "
                "SET n.type = $type, n.updated_at = $ts",
                uid=user_id, name=keep_name, type=keep_type, ts=ts,
            )
            for del_name in to_delete:
                await session.run(
                    "MATCH (dup:Entity {user_id: $uid, name: $del_name})-[r:RELATED_TO]->(target:Entity {user_id: $uid}) "
                    "MATCH (keep:Entity {user_id: $uid, name: $keep_name}) "
                    "MERGE (keep)-[:RELATED_TO {type: r.type}]->(target) "
                    "DELETE r",
                    uid=user_id, keep_name=keep_name, del_name=del_name,
                )
                await session.run(
                    "MATCH (source:Entity {user_id: $uid})-[r:RELATED_TO]->(dup:Entity {user_id: $uid, name: $del_name}) "
                    "MATCH (keep:Entity {user_id: $uid, name: $keep_name}) "
                    "MERGE (source)-[:RELATED_TO {type: r.type}]->(keep) "
                    "DELETE r",
                    uid=user_id, keep_name=keep_name, del_name=del_name,
                )
                await session.run(
                    "MATCH (n:Entity {user_id: $uid, name: $del_name}) DETACH DELETE n",
                    uid=user_id, del_name=del_name,
                )
            merged += len(to_delete)

    if merged > 0:
        await _cache_del_user(user_id)

    return merged


async def query_context(user_id: int, query_text: str, limit: int = 50, min_score: float = 0.5) -> str:
    driver = get_driver()
    if not driver:
        return ""

    words = [w for w in query_text.split() if len(w) > 2]
    if not words:
        return ""

    cache_key = _cache_key(user_id, f"ctx:{query_text}:{limit}:{min_score}")
    cached = await _cache_get(cache_key)
    if cached is not None:
        return cached

    ft_query = " ".join(words)

    try:
        async with driver.session() as session:
            result = await session.run(
                "CALL db.index.fulltext.queryNodes('entity_name_ft', $ft) YIELD node AS e, score "
                "WHERE e.user_id = $uid AND score >= $min_score "
                "WITH e, score "
                "OPTIONAL MATCH (e)-[r:RELATED_TO]->(other:Entity {user_id: $uid}) "
                "RETURN e.name AS name, e.type AS type, score, "
                "       collect({rel: r.type, target: other.name}) AS rels "
                "ORDER BY score DESC LIMIT $limit",
                uid=user_id, ft=ft_query, limit=limit, min_score=min_score,
            )
            rows = await result.data()

        if not rows:
            return ""

        lines = []
        for row in rows:
            line = f"- {row['name']} ({row['type']})"
            rels = [r for r in (row.get("rels") or []) if r.get("target")]
            if rels:
                line += ": " + ", ".join(f"{r['rel']} {r['target']}" for r in rels[:4])
            lines.append(line)

        output = "\n".join(lines)
        await _cache_set(cache_key, output)
        return output

    except Exception:
        logger.exception("[graph] query_context failed user=%d", user_id)
        return ""


async def query_by_term(user_id: int, term: str, limit: int = 10, min_score: float = 0.5) -> str:
    return await query_context(user_id, term, limit=limit, min_score=min_score)


async def query_by_keywords(user_id: int, query_text: str, limit: int = 30) -> str:
    driver = get_driver()
    if not driver:
        return ""

    words = [w for w in query_text.split() if len(w) > 2 and w.lower() not in _STOPWORDS]
    if not words:
        return ""

    cache_key = _cache_key(user_id, f"kw:{query_text}:{limit}")
    cached = await _cache_get(cache_key)
    if cached is not None:
        return cached

    ft_query = " ".join(words)

    try:
        async with driver.session() as session:
            result = await session.run(
                "CALL db.index.fulltext.queryNodes('entity_name_ft', $ft) YIELD node AS e, score "
                "WHERE e.user_id = $uid "
                "OPTIONAL MATCH (e)-[r:RELATED_TO]->(other:Entity {user_id: $uid}) "
                "RETURN e.name AS source, r.type AS rel, other.name AS target, score "
                "ORDER BY score DESC LIMIT $limit",
                uid=user_id, ft=ft_query, limit=limit,
            )
            rows = await result.data()

        if not rows:
            return ""

        lines = []
        seen = set()
        for row in rows:
            src = row.get("source")
            rel = row.get("rel")
            tgt = row.get("target")
            if not src or not rel or not tgt:
                continue
            edge = (src, rel, tgt)
            if edge in seen:
                continue
            seen.add(edge)
            lines.append(f"{src} --[{rel}]→ {tgt}")

        if not lines:
            return ""

        output = "\n".join(lines)
        await _cache_set(cache_key, output)
        return output

    except Exception:
        logger.exception("[graph] query_by_keywords failed user=%d", user_id)
        return ""
