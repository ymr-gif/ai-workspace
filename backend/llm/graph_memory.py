import json
import logging
from datetime import datetime, timezone

from config import MODELS
from core.neo4j_client import get_driver

logger = logging.getLogger("graph_memory")

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
            model=MODELS["llama"],
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

        async with driver.session() as session:
            for e in entities:
                name  = (e.get("name") or "").strip()
                etype = (e.get("type") or "OTHER").strip()
                if not name:
                    continue
                await session.run(
                    "MERGE (e:Entity {user_id: $uid, name: $name}) "
                    "SET e.type = $type, e.updated_at = $ts",
                    uid=user_id, name=name, type=etype, ts=now,
                )

            valid_names = {(e.get("name") or "").strip() for e in entities}
            for r in relations:
                src   = (r.get("from") or "").strip()
                dst   = (r.get("to")   or "").strip()
                rtype = (r.get("type") or "RELATED_TO").strip().upper().replace(" ", "_")
                if not src or not dst or src not in valid_names or dst not in valid_names:
                    continue
                await session.run(
                    "MATCH (a:Entity {user_id: $uid, name: $src}), "
                    "      (b:Entity {user_id: $uid, name: $dst}) "
                    "MERGE (a)-[rel:RELATED_TO {type: $rtype}]->(b) "
                    "SET rel.updated_at = $ts",
                    uid=user_id, src=src, dst=dst, rtype=rtype, ts=now,
                )

        logger.info("[graph] stored %d entities %d rels user=%d", len(entities), len(relations), user_id)

    except json.JSONDecodeError:
        logger.debug("[graph] LLM returned non-JSON, skipping")
    except Exception:
        logger.exception("[graph] extract_and_store failed user=%d", user_id)


async def query_context(user_id: int, query_text: str, limit: int = 50, min_score: float = 0.5) -> str:
    driver = get_driver()
    if not driver:
        return ""

    words = [w for w in query_text.split() if len(w) > 2]
    if not words:
        return ""

    ft_query = " ".join(words)

    try:
        async with driver.session() as session:
            result = await session.run(
                "CALL db.index.fulltext.queryNodes('entity_name_ft', $query) YIELD node AS e, score "
                "WHERE e.user_id = $uid AND score >= $min_score "
                "OPTIONAL MATCH (e)-[r:RELATED_TO]->(other:Entity {user_id: $uid}) "
                "RETURN e.name AS name, e.type AS type, "
                "       collect({rel: r.type, target: other.name}) AS rels "
                "ORDER BY score DESC LIMIT $limit",
                uid=user_id, query=ft_query, limit=limit, min_score=min_score,
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

        return "\n".join(lines)

    except Exception:
        logger.exception("[graph] query_context failed user=%d", user_id)
        return ""


async def query_by_term(user_id: int, term: str, limit: int = 10, min_score: float = 0.5) -> str:
    return await query_context(user_id, term, limit=limit, min_score=min_score)
