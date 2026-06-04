import json
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Message, ToolCallLog

from .file_ops import (
    _list_files, _read_file, _write_file, _create_file,
    _append_to_file, _patch_file,
)
from .search import _search_in_file, _search_across_files
from agent.canvas_graph import (
    create_node, delete_node, update_node, find_nodes,
    wire_nodes, unwire_nodes, query_canvas, get_canvas_graph,
)

logger = logging.getLogger("tools")

ASK_USER_PREFIX = "__ASK_USER__:"
CONFIRM_WRITE_PREFIX = "__CONFIRM_WRITE_MEMORY__:"

# ── Creation guard constants ──────────────────────────────────────

_CREATION_RE = [
    re.compile(r"(create|new|make|start|set\s*up|setup)\s*.{0,30}\s*(session|conversation)", re.I),
    re.compile(r"(session|conversation)\s*.{0,10}\s*(create|new)", re.I),
]
_NEGATION_RE = re.compile(r"don'?t\s+(create|make|add)|never\s*mind|cancel|forget\s+it|scratch\s+that", re.I)
_CONFIRMATION_RE = re.compile(
    r"yes|yeah|sure|confirm|create|do\s*it|proceed|go\s*ahead|make\s*it|let'?s\s+do|okay?\b|please|that\s+sounds|agree|approved|start",
    re.I,
)
_CREATION_FLOW_TTL = 300

_FLOW_STATE_PENDING = "pending_specs"
_FLOW_STATE_CONFIRMED = "confirmed"

_CREATION_REJECT_SESSION = (
    "Cannot create session: the user didn't request one. "
    "This tool creates real database records — only call it when the user explicitly asks to create a session. "
    "Do not call this tool again. Answer the user's message normally instead."
)
_CREATION_NOT_CONFIRMED = (
    "The user hasn't confirmed yet. Do not call this tool again — "
    "answer the user's message normally and wait for their explicit confirmation."
)


async def execute_tool(
    name:    str,
    args:    dict,
    db:      AsyncSession,
    user_id: int,
    conv_id: uuid.UUID,
) -> str:
    result = f"Unknown tool: {name}"
    try:
        if name == "list_files":
            result = await _list_files(db, conv_id)
        elif name == "read_file":
            result = await _read_file(db, user_id, uuid.UUID(args["file_id"]))
        elif name == "write_file":
            result = await _write_file(db, user_id, uuid.UUID(args["file_id"]), args["content"])
        elif name == "create_file":
            result = await _create_file(db, user_id, conv_id, args["name"], args["content"])
        elif name == "append_to_file":
            result = await _append_to_file(db, user_id, uuid.UUID(args["file_id"]), args["content"])
        elif name == "patch_file":
            result = await _patch_file(db, user_id, uuid.UUID(args["file_id"]), args["old_text"], args["new_text"])
        elif name == "search_in_file":
            result = await _search_in_file(db, user_id, uuid.UUID(args["file_id"]), args["query"])
        elif name == "search_across_files":
            result = await _search_across_files(db, conv_id, args["query"])
        elif name == "ask_user":
            result = f"{ASK_USER_PREFIX}{args.get('question', '')}"
        elif name == "write_memory":
            result = f"{CONFIRM_WRITE_PREFIX}{args.get('fact', '')}"
        elif name == "query_graph":
            from llm.graph_memory import query_by_term
            term   = args.get("query", "")
            result = (await query_by_term(user_id, term)) or "No entities found for that query."
        elif name == "create_canvas_node":
            result = await create_node(user_id, args["node_type"], args.get("config"))
        elif name == "delete_canvas_node":
            result = await delete_node(user_id, args["node_id"])
        elif name == "update_canvas_node":
            result = await update_node(user_id, args["node_id"], args.get("config"), args.get("status"))
        elif name == "wire_nodes":
            result = await wire_nodes(user_id, args["src_id"], args["dst_id"], args["src_port"], args["dst_port"], args["relation"])
        elif name == "unwire_nodes":
            result = await unwire_nodes(user_id, args["src_id"], args["dst_id"])
        elif name == "query_canvas":
            result = await query_canvas(user_id, args["cypher"])
        elif name == "get_canvas_graph":
            result = await get_canvas_graph(user_id)
        elif name == "create_conversation":
            _guard = await _run_creation_guard(db, conv_id, "session")
            if isinstance(_guard, str):
                result = _guard
            else:
                import uuid as _uuid
                from core.db import AsyncSessionLocal
                from models import Conversation as _Conv

                async with AsyncSessionLocal() as _db:
                    _conv = _Conv(
                        id=_uuid.uuid4(), user_id=user_id,
                        title=args.get("title", "Session"),
                        memory_enabled=True,
                    )
                    _db.add(_conv)
                    await _db.commit()
                    result = str(_conv.id)

                await _ensure_creation_wiring(user_id, result, "session", {"conversation_id": result})
                await _clear_creation_flow(conv_id)
    except Exception as e:
        logger.warning("[tools] execute_tool failed name=%s err=%s", name, e)
        result = f"Error: {e}"

    if result is None:
        result = "ok"
    elif not isinstance(result, str):
        result = json.dumps(result)

    try:
        preview = result if (result.startswith(ASK_USER_PREFIX) or result.startswith(CONFIRM_WRITE_PREFIX)) else result[:500]
        db.add(ToolCallLog(
            user_id=user_id,
            conversation_id=conv_id,
            tool_name=name,
            args=args,
            result_preview=preview,
        ))
        await db.flush()
    except Exception:
        pass

    return result


# ── Creation guard: 3-layer state machine ─────────────────────────


# Canvas tools (read AND write) are withheld unless the message names a canvas
# object. The 70B otherwise treats every benign turn as a canvas task and loops:
# gating write tools alone just makes it spin on read-only get_canvas_graph /
# query_canvas until MAX_TOOL_ITERATIONS (J1). With no canvas tools offered it
# answers conversationally. "what's on my canvas?" matches → tools restored.
_CANVAS_INTENT_RE = re.compile(
    r"\b(canvas|nodes?|sessions?|conversations?|wires?|unwire|connect|disconnect|graph)\b",
    re.I,
)


async def canvas_context_active(message: str, conv_id: uuid.UUID | None) -> bool:
    """Should canvas tools be offered to the model this turn?

    True only when the current message references a canvas object (node,
    session, wire, …) or a creation flow is mid-confirmation (Redis state set).
    Otherwise all canvas tools are withheld — if none are offered, the model
    cannot loop on them and must answer in text.
    """
    text = message or ""
    if _CANVAS_INTENT_RE.search(text):
        return True
    if conv_id is not None and await _get_flow_state(conv_id) is not None:
        return True
    return False


async def _run_creation_guard(
    db: AsyncSession,
    conv_id: uuid.UUID,
    create_type: str,  # "session"
) -> str | bool:
    """Run the 3-layer creation guard.

    Returns True to allow creation, or a string rejection/ASK_USER_PREFIX message.
    """
    noun = "session"
    reject = _CREATION_REJECT_SESSION

    # ── Layer 1: Redis flow state ──────────────────────────────────
    state = await _get_flow_state(conv_id)

    if state == _FLOW_STATE_CONFIRMED:
        return True

    if state == _FLOW_STATE_PENDING:
        # ── Layer 3: message pairing — the confirm turn's message is "yes",
        # which carries no creation intent of its own; gate on the affirmative
        # reply after the ask, NOT on re-detecting creation intent. (Canvas
        # tool gating in the service layer prevents stale-state leaks.)
        if await _user_replied_after_ask(db, conv_id):
            await _set_flow_state(conv_id, _FLOW_STATE_CONFIRMED)
            return True
        return _CREATION_NOT_CONFIRMED

    # ── Layer 2: user intent in recent messages ────────────────────
    if await _user_requested_creation(db, conv_id, noun):
        await _set_flow_state(conv_id, _FLOW_STATE_PENDING)
        return (
            f"{ASK_USER_PREFIX}I need your confirmation to create a new {noun}. "
            f"Please provide a title."
        )

    return reject


async def _user_requested_creation(
    db: AsyncSession,
    conv_id: uuid.UUID,
    noun: str,  # "session"
) -> bool:
    """Layer 2: check the LATEST user message for creation intent.

    Only the most recent message matters — old intent from prior turns
    is not re-detected on every tool call.
    """
    try:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id, Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        msg = result.scalars().first()
    except Exception:
        return False
    if msg is None:
        return False

    text = msg.content or ""
    if _NEGATION_RE.search(text):
        return False
    if any(p.search(text) for p in _CREATION_RE):
        if noun in text.lower() or re.search(r"(create|new|make|start)\s*(one|a|an|the|this|some)", text.lower()):
            return True
    return False


async def _user_replied_after_ask(
    db: AsyncSession,
    conv_id: uuid.UUID,
) -> bool:
    """Layer 3: check if user confirmed after the last ask_user assistant msg.

    The reply must contain affirmative intent — not just any message.
    """
    try:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc())
            .limit(4)
        )
        messages = list(reversed(result.scalars().all()))
    except Exception:
        return False

    found_ask = False
    for m in messages:
        if m.role == "assistant" and "I need your confirmation" in (m.content or ""):
            found_ask = True
        elif found_ask and m.role == "user":
            return bool(_CONFIRMATION_RE.search(m.content or ""))

    return False


async def _get_flow_state(conv_id: uuid.UUID) -> str | None:
    """Layer 1: read Redis creation flow state."""
    from config import USE_REDIS
    if not USE_REDIS:
        return None
    try:
        from core.redis_client import get_redis
        r = get_redis()
        val = await r.get(f"creation_flow:{conv_id}")
        if val:
            data = json.loads(val)
            return data.get("state")
    except Exception:
        pass
    return None


async def _set_flow_state(conv_id: uuid.UUID, state: str) -> None:
    """Layer 1: write Redis creation flow state."""
    from config import USE_REDIS
    if not USE_REDIS:
        return
    try:
        from core.redis_client import get_redis
        r = get_redis()
        await r.setex(
            f"creation_flow:{conv_id}",
            _CREATION_FLOW_TTL,
            json.dumps({"state": state}),
        )
    except Exception:
        pass


async def _clear_creation_flow(conv_id: uuid.UUID) -> None:
    """Layer 1: delete Redis creation flow state (after successful creation)."""
    from config import USE_REDIS
    if not USE_REDIS:
        return
    try:
        from core.redis_client import get_redis
        r = get_redis()
        await r.delete(f"creation_flow:{conv_id}")
    except Exception:
        pass


async def _ensure_creation_wiring(
    user_id: int,
    db_id: str,
    node_type: str,
    node_config: dict,
) -> None:
    """Create matching session canvas node + wire to input node."""
    try:
        existing = await find_nodes(user_id, node_type)
        node = next(
            (n for n in existing
             if n.get("config", {}).get("conversation_id") == db_id),
            None,
        )
        # H4: mark AI/user-created sessions as kind="user" (distinct from the
        # permanent [GLOBAL] JARVIS session created by _ensure_canvas_wiring)
        node_config.setdefault("kind", "user")
        if node:
            node_id = node["node_id"]
        else:
            # internal=True: trusted bootstrap — runs only after the creation guard
            # passed and a real Postgres Conversation row exists, so it may create
            # the permanent session node that the AI tool path is blocked from.
            node_id = await create_node(user_id, node_type, node_config, internal=True)

        inputs = await find_nodes(user_id, "input")
        if not inputs:
            input_id = await create_node(user_id, "input", {}, internal=True)
        else:
            input_id = inputs[0]["node_id"]

        graph = await get_canvas_graph(user_id)
        already_wired = any(
            w["src_id"] == input_id and w["dst_id"] == node_id
            for w in graph["wires"]
        )
        if not already_wired:
            await wire_nodes(
                user_id, input_id, node_id,
                "routed_message", "message", "routes_to",
            )
    except Exception as e:
        # Broad catch: a wiring failure must never break the (already-committed)
        # create_conversation success. But log the real cause + type —
        # a bare "auto-wire failed" hid the I2 permanent-type-guard regression.
        logger.warning(
            "[tools] auto-wire failed user=%d type=%s id=%s err=%s: %s",
            user_id, node_type, db_id, type(e).__name__, e,
        )
