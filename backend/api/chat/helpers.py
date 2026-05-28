import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODELS
from llm import retriever
from llm.embeddings import embed as embed_text
from llm.router import classify_query
from llm.retriever.policy import get_policy
from llm.summarizer.salience import compute_salience
from models import Conversation, MemoryConflict, Message, User, UserMemory, Workspace, WorkspaceMemory

from .schemas import ChatRequest

logger = logging.getLogger("chat")


def _resolve_model(name: str | None) -> str | None:
    if not name:
        return None
    if name in MODELS:
        return MODELS[name]
    if name in MODELS.values():
        return name
    return None


def _estimate_tokens(*texts: str) -> int:
    return sum(len(t) // 4 for t in texts if t)


def _extract_model_params(req: ChatRequest) -> dict | None:
    p: dict = {}
    if req.temperature is not None: p["temperature"] = req.temperature
    if req.max_tokens  is not None: p["max_tokens"]  = req.max_tokens
    if req.top_p       is not None: p["top_p"]       = req.top_p
    return p or None


async def _check_cost_cap(user: User, db: AsyncSession) -> None:
    if user.cost_limit_usd is None:
        return
    q = (
        select(func.coalesce(func.sum(Message.cost_usd), 0.0).label("total"))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == user.id, Message.role == "assistant")
    )
    if user.cost_window_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=user.cost_window_days)
        q = q.where(Message.created_at >= cutoff)
    row   = await db.execute(q)
    total = float(row.scalar_one() or 0.0)
    if total >= user.cost_limit_usd:
        window_label = f"{user.cost_window_days}d" if user.cost_window_days else "all-time"
        raise HTTPException(
            status_code=402,
            detail=f"Cost cap reached (${total:.6f} / ${user.cost_limit_usd:.6f} {window_label}). Contact admin.",
        )


async def _resolve_conversation(
    req:          ChatRequest,
    current_user: User,
    db:           AsyncSession,
) -> Conversation:
    if req.conversation_id:
        try:
            cid = uuid.UUID(req.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id")
        conv = await db.get(Conversation, cid)
        if not conv or conv.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv

    workspace_id: uuid.UUID | None = None
    if req.workspace_id:
        try:
            wid = uuid.UUID(req.workspace_id)
            ws  = await db.get(Workspace, wid)
            if ws and ws.user_id == current_user.id:
                workspace_id = wid
        except ValueError:
            pass
    if workspace_id is None:
        result = await db.execute(
            select(Workspace)
            .where(Workspace.user_id == current_user.id, Workspace.name == "Default")
            .limit(1)
        )
        default_ws = result.scalar_one_or_none()
        if default_ws:
            workspace_id = default_ws.id

    conv = Conversation(user_id=current_user.id, title=req.message[:60].strip(), workspace_id=workspace_id)
    db.add(conv)
    await db.flush()
    return conv


async def _build_stream_context(
    req:          ChatRequest,
    conv:         Conversation,
    current_user: User,
    db:           AsyncSession,
    rid:          str,
) -> dict:
    memory_row      = await db.get(UserMemory, current_user.id)
    memory_enabled  = conv.memory_enabled
    memory_sheet    = (memory_row.content         if memory_row and memory_row.content         else "") if memory_enabled else ""
    project_summary = (memory_row.project_summary if memory_row and memory_row.project_summary else "") if memory_enabled else ""

    if memory_row and memory_enabled:
        memory_row.salience   = compute_salience(memory_row.salience, access_count=1)
        memory_row.last_used_at = datetime.now(timezone.utc)

    is_ref    = retriever.is_reference_query(req.message)
    query_type = classify_query(req.message)
    policy     = get_policy(query_type)

    embed_task = None
    if req.conversation_id or is_ref:
        embed_task = asyncio.create_task(embed_text(req.message, input_type="query"))

    history_summary = conv.history_summary or ""
    candidates: list = []
    if req.conversation_id:
        cand_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(30)
        )
        candidates = list(reversed(cand_result.scalars().all()))

    query_emb = (await embed_task) if embed_task else None

    history: list[dict] = []
    if candidates:
        relevance_map: dict = {}
        if query_emb:
            candidate_ids = [m.id for m in candidates]
            relevance_map = await retriever.get_relevance_scores(db, conv.id, query_emb, candidate_ids)
        n = len(candidates)
        scored = []
        for i, m in enumerate(candidates):
            recency   = i / max(n - 1, 1)
            relevance = relevance_map.get(m.id, 0.0)
            scored.append((0.6 * recency + 0.4 * relevance, i, m))
        scored.sort(key=lambda x: -x[0])
        top_msgs = [m for _, _, m in scored[:10]]
        top_msgs.sort(key=lambda m: m.created_at)
        history = [{"role": m.role, "content": m.content} for m in top_msgs]

    top_k     = max(policy["top_k"], 8 if is_ref else 0)
    retrieved: list[str] = []
    if query_emb:
        retrieved = await retriever.retrieve(
            db, query_emb, conv.id,
            top_k=top_k, query_text=req.message,
            fusion_mode=policy["fusion_mode"], k_dense=policy["k_dense"],
            k_sparse=policy["k_sparse"], alpha=policy["alpha"],
        )
        if is_ref and not retrieved:
            retrieved = await retriever.retrieve_global(
                db, query_emb, conv.id, current_user.id,
                query_text=req.message,
                fusion_mode=policy["fusion_mode"], k_dense=policy["k_dense"],
                k_sparse=policy["k_sparse"], alpha=policy["alpha"],
            )

    file_chunks: list[str] = []
    file_names:  list[str] = []
    file_ids:    list      = []
    if req.conversation_id:
        file_ids, file_names = await retriever.get_conversation_files(db, conv.id)
        if file_ids:
            if query_emb:
                file_chunks = await retriever.retrieve_from_files(
                    db, query_emb, file_ids,
                    top_k=policy["top_k"], query_text=req.message,
                    fusion_mode=policy["fusion_mode"], k_dense=policy["k_dense"],
                    k_sparse=policy["k_sparse"], alpha=policy["alpha"],
                )
            else:
                file_chunks = await retriever.retrieve_files_sequential(db, file_ids, top_k=10)
            if file_chunks:
                for i, chunk in enumerate(file_chunks):
                    preview = chunk["content"][:120] if isinstance(chunk, dict) else chunk[:120]
                    logger.info("[file_ctx] rid=%s chunk=%d/%d chunk_id=%s source_id=%s score=%.6f preview=%s",
                                rid, i + 1, len(file_chunks),
                                chunk.get("chunk_id") if isinstance(chunk, dict) else None,
                                chunk.get("source_id") if isinstance(chunk, dict) else None,
                                chunk.get("final_score", 0.0) if isinstance(chunk, dict) else 0.0,
                                repr(preview))
            else:
                logger.warning("[file_ctx] rid=%s file_ids=%d but NO chunks retrieved", rid, len(file_ids))

    workspace_memory    = ""
    workspace_sysprompt = None
    if conv.workspace_id:
        ws = await db.get(Workspace, conv.workspace_id)
        if ws:
            workspace_sysprompt = ws.system_prompt or None
            ws_mem_row = await db.execute(
                select(WorkspaceMemory).where(WorkspaceMemory.workspace_id == conv.workspace_id)
            )
            ws_mem = ws_mem_row.scalar_one_or_none()
            if ws_mem and ws_mem.content:
                workspace_memory = ws_mem.content

    conflicted_facts: frozenset[str] = frozenset()
    if memory_enabled and memory_sheet:
        result = await db.execute(
            select(MemoryConflict)
            .where(MemoryConflict.user_id == current_user.id, MemoryConflict.resolution == "unresolved")
        )
        conflicts = result.scalars().all()
        if conflicts:
            conflicted_facts = frozenset(
                f for c in conflicts for f in (c.fact_a, c.fact_b)
            )

    graph_context = ""
    graph_facts   = ""
    if memory_enabled:
        try:
            from llm.graph_memory import query_context as graph_query
            graph_context = await graph_query(current_user.id, req.message, limit=50)
        except Exception:
            logger.exception("[graph] query_context failed")
        try:
            from llm.graph_memory import query_by_keywords
            graph_facts = await query_by_keywords(current_user.id, req.message)
        except Exception:
            logger.exception("[graph] query_by_keywords failed")

    logger.info("[policy] rid=%s query_type=%s fusion=%s alpha=%s k_dense=%d k_sparse=%d top_k=%d",
                rid, query_type, policy["fusion_mode"], policy["alpha"],
                policy["k_dense"], policy["k_sparse"], policy["top_k"])

    return {
        "memory_enabled":      memory_enabled,
        "memory_sheet":        memory_sheet,
        "project_summary":     project_summary,
        "history_summary":     history_summary,
        "history":             history,
        "retrieved":           retrieved,
        "file_chunks":         file_chunks,
        "file_names":          file_names,
        "file_ids":            file_ids,
        "workspace_memory":    workspace_memory,
        "workspace_sysprompt": workspace_sysprompt,
        "graph_context":       graph_context,
        "graph_facts":         graph_facts,
        "conflicted_facts":    conflicted_facts,
        "policy_used":         query_type,
    }
