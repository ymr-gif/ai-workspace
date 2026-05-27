import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MODEL_PRICING, MODELS
from llm import retriever
from llm.embeddings import embed as embed_text
from models import Conversation, Message, User, UserMemory, Workspace, WorkspaceMemory

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


async def _embed_exchange(
    message_id:      uuid.UUID,
    conversation_id: uuid.UUID,
    user_text:       str,
    assistant_text:  str,
) -> None:
    try:
        exchange = f"{user_text[:300]}\n{assistant_text[:400]}"
        emb = await embed_text(exchange, input_type="passage")
        if emb:
            await retriever.store_exchange(message_id, conversation_id, user_text, assistant_text, emb)
    except Exception:
        logger.exception("[embed_exchange] failed msg=%s", message_id)


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

    # Resolve workspace for new conversation
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
        # Fall back to user's Default workspace
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

    is_ref = retriever.is_reference_query(req.message)

    # Start embedding concurrently — HTTP call; runs while DB queries execute below
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

    # Collect embedding — ran concurrently with the DB query above
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

    top_k     = 8 if is_ref else 3
    retrieved: list[str] = []
    if query_emb:
        retrieved = await retriever.retrieve(db, query_emb, conv.id, top_k=top_k, query_text=req.message)
        if is_ref and not retrieved:
            retrieved = await retriever.retrieve_global(db, query_emb, conv.id, current_user.id, query_text=req.message)

    file_chunks: list[str] = []
    file_names:  list[str] = []
    file_ids:    list      = []
    if req.conversation_id:
        file_ids, file_names = await retriever.get_conversation_files(db, conv.id)
        if file_ids:
            if query_emb:
                file_chunks = await retriever.retrieve_from_files(db, query_emb, file_ids, top_k=5, query_text=req.message)
            else:
                file_chunks = await retriever.retrieve_files_sequential(db, file_ids, top_k=10)
            if file_chunks:
                for i, chunk in enumerate(file_chunks):
                    logger.info("[file_ctx] rid=%s chunk=%d/%d preview=%s",
                                rid, i + 1, len(file_chunks), repr(chunk[:120]))
            else:
                logger.warning("[file_ctx] rid=%s file_ids=%d but NO chunks retrieved", rid, len(file_ids))

    # Load workspace memory if conversation belongs to a workspace
    workspace_memory   = ""
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
    }


async def _generate_proactive(user_msg: str, ai_msg: str) -> str | None:
    from llm.agency import generate_proactive_suggestion
    try:
        return await generate_proactive_suggestion(user_msg, ai_msg)
    except Exception:
        logger.exception("[proactive] failed")
        return None


async def _auto_title(conv_id: uuid.UUID, user_msg: str, ai_msg: str) -> None:
    from core.db import AsyncSessionLocal
    from llm.nim import call
    prompt = (
        f"Summarize this exchange in 6 words or fewer:\n"
        f"User: {user_msg[:200]}\nAI: {ai_msg[:200]}"
    )
    try:
        result = await call(
            model      = MODELS["llama"],
            messages   = [{"role": "user", "content": prompt}],
            request_id = f"title-{conv_id}",
        )
        title = (result.get("content") or "").strip().strip('"').strip("'")
        if title and len(title) <= 80:
            async with AsyncSessionLocal() as db:
                conv = await db.get(Conversation, conv_id)
                if conv:
                    conv.title = title
                    await db.commit()
    except Exception:
        logger.exception("[auto_title] failed conv=%s", conv_id)


def _calculate_tokens_and_cost(
    event:       dict,
    ctx:         dict,
    req:         ChatRequest,
    full_response: str,
    model_used:  str,
) -> tuple[int, int, int, float]:
    pricing = MODEL_PRICING.get(model_used, {})
    nim_usage = event.get("usage")
    if nim_usage and isinstance(nim_usage, dict):
        prompt_tokens     = nim_usage.get("prompt_tokens", 0)
        completion_tokens = nim_usage.get("completion_tokens", 0)
        total_tokens      = nim_usage.get("total_tokens", prompt_tokens + completion_tokens)
    else:
        prompt_tokens     = _estimate_tokens(
            ctx["memory_sheet"], ctx["project_summary"],
            ctx["history_summary"],
            *[m["content"] for m in ctx["history"]],
            req.message,
        )
        completion_tokens = len(full_response) // 4
        total_tokens      = prompt_tokens + completion_tokens
    cost_usd = (
        prompt_tokens     / 1_000_000 * pricing.get("input",  0.0) +
        completion_tokens / 1_000_000 * pricing.get("output", 0.0)
    )
    return prompt_tokens, completion_tokens, total_tokens, cost_usd
