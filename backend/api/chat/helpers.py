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
from llm.summarizer.salience import bump_fact_saliences, compute_salience, score_facts
from models import Conversation, File, MemoryConflict, Message, User, UserGoal, UserMemory, Workspace, WorkspaceMemory

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
    memory_sheet    = (memory_row.content         if memory_row and memory_row.content         else "")
    project_summary = (memory_row.project_summary if memory_row and memory_row.project_summary else "")

    if memory_row:
        memory_row.salience   = compute_salience(memory_row.salience, access_count=1)
        memory_row.last_used_at = datetime.now(timezone.utc)

        fact_saliences = memory_row.fact_saliences or {}

        # Time-based decay for ranking only — not written back to DB
        ranking_saliences = fact_saliences
        if memory_row.last_summarized_at:
            hours_since = max(0.0, (datetime.now(timezone.utc) - memory_row.last_summarized_at).total_seconds() / 3600)
            time_decay = 0.95 ** (hours_since / 24)
            if time_decay < 0.999:
                ranking_saliences = {k: round(v * time_decay, 4) for k, v in fact_saliences.items()}

        scored_facts = score_facts(memory_sheet, ranking_saliences)
        loaded_facts = [f for f, _ in scored_facts[:20]]
        memory_sheet = "\n".join(loaded_facts)
        memory_row.fact_saliences = bump_fact_saliences(loaded_facts, fact_saliences)
        logger.info("[salience] rid=%s facts_loaded=%d top_fact_score=%.4f bottom_fact_score=%.4f",
                    rid, len(loaded_facts),
                    scored_facts[0][1] if scored_facts else 0.0,
                    scored_facts[-1][1] if scored_facts else 0.0)
    else:
        fact_saliences = {}

    is_ref    = retriever.is_reference_query(req.message)
    query_type = classify_query(req.message)
    policy     = get_policy(query_type)

    embed_task = None
    if req.conversation_id or is_ref or req.file_ids:
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

    if memory_row and retrieved:
        salience_mult = 1.0 + min(memory_row.salience, 2.0) * 0.05
        for c in retrieved:
            c["final_score"] = c.get("final_score", 0.0) * salience_mult
        retrieved.sort(key=lambda c: -c.get("final_score", 0.0))
        logger.info("[salience] rid=%s reranked chunks=%d memory_salience=%.4f",
                    rid, len(retrieved), memory_row.salience)

    file_chunks: list[str] = []
    file_names:  list[str] = []
    file_ids:    list      = []

    req_fids: list = []
    for fid in (req.file_ids or []):
        try:
            req_fids.append(uuid.UUID(fid))
        except ValueError:
            pass

    if req.conversation_id:
        conv_ids, conv_names = await retriever.get_conversation_files(db, conv.id)
        extra = [fid for fid in req_fids if fid not in set(conv_ids)]
        if extra:
            name_res = await db.execute(
                select(File.id, File.filename)
                .where(File.id.in_(extra), File.user_id == current_user.id)
            )
            name_map   = {row[0]: row[1] for row in name_res.all()}
            safe_extra = [fid for fid in extra if fid in name_map]
            file_ids   = conv_ids + safe_extra
            file_names = list(conv_names) + [name_map[fid] for fid in safe_extra]
        else:
            file_ids, file_names = conv_ids, conv_names
    elif req_fids:
        name_res = await db.execute(
            select(File.id, File.filename)
            .where(File.id.in_(req_fids), File.user_id == current_user.id)
        )
        name_map   = {row[0]: row[1] for row in name_res.all()}
        file_ids   = [fid for fid in req_fids if fid in name_map]
        file_names = [name_map[fid] for fid in file_ids]

    if file_ids:
        if query_emb:
            file_chunks = await retriever.retrieve_from_files(
                db, query_emb, file_ids,
                top_k=policy["top_k"], query_text=req.message,
                fusion_mode=policy["fusion_mode"], k_dense=policy["k_dense"],
                k_sparse=policy["k_sparse"], alpha=policy["alpha"],
            )
            if memory_row and file_chunks:
                fs_mult = 1.0 + min(memory_row.salience, 2.0) * 0.05
                for c in file_chunks:
                    c["final_score"] = c.get("final_score", 0.0) * fs_mult
                file_chunks.sort(key=lambda c: -c.get("final_score", 0.0))
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
    if memory_sheet:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(MemoryConflict)
            .where(MemoryConflict.user_id == current_user.id, MemoryConflict.resolution == "unresolved")
        )
        conflicts = result.scalars().all()
        active = []
        for c in conflicts:
            if c.expires_at and c.expires_at <= now:
                c.resolution  = "keep_a"
                c.resolved_at = now
            else:
                active.append(c)
        if any(c.expires_at and c.expires_at <= now for c in conflicts):
            await db.commit()
        if active:
            conflicted_facts = frozenset(
                f for c in active for f in (c.fact_a, c.fact_b)
            )

    last_session = ""
    if not req.conversation_id:
        ls_result = await db.execute(
            select(Conversation.title, Conversation.updated_at)
            .where(Conversation.user_id == current_user.id, Conversation.id != conv.id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        ls_row = ls_result.first()
        if ls_row and ls_row.title:
            elapsed = datetime.now(timezone.utc) - ls_row.updated_at
            hours = elapsed.total_seconds() / 3600
            if hours < 1:
                ago = f"{max(1, int(elapsed.total_seconds() / 60))} minutes ago"
            elif hours < 24:
                ago = f"{int(hours)} hours ago"
            else:
                ago = f"{int(hours / 24)} days ago"
            last_session = f'Last session: "{ls_row.title}" — {ago}'

    graph_context = ""
    graph_facts   = ""
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

    active_goals = ""
    try:
        goals_result = await db.execute(
            select(UserGoal)
            .where(UserGoal.user_id == current_user.id, UserGoal.status == "active")
            .order_by(UserGoal.created_at.asc())
        )
        goals = goals_result.scalars().all()
        if goals:
            lines = [f"{i+1}. {g.title}" + (f" — {g.description}" if g.description else "") for i, g in enumerate(goals)]
            active_goals = "\n".join(lines)
    except Exception:
        logger.exception("[goals] query failed")

    logger.info("[policy] rid=%s query_type=%s fusion=%s alpha=%s k_dense=%d k_sparse=%d top_k=%d",
                rid, query_type, policy["fusion_mode"], policy["alpha"],
                policy["k_dense"], policy["k_sparse"], policy["top_k"])

    return {
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
        "active_goals":        active_goals,
        "conflicted_facts":    conflicted_facts,
        "policy_used":         query_type,
        "fact_saliences":      fact_saliences,
        "last_session":        last_session,
    }
