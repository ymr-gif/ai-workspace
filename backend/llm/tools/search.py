import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ConversationFile, File as FileModel
from llm.embeddings import embed
from llm.retriever import retrieve_from_files

logger = logging.getLogger("tools")


async def _search_in_file(
    db:      AsyncSession,
    user_id: int,
    file_id: uuid.UUID,
    query:   str,
) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    query_emb = await embed(query, input_type="query")
    if not query_emb:
        return "Error: could not embed query (embedding API unavailable)."
    chunks = await retrieve_from_files(db, query_emb, [file_id], top_k=10)
    if not chunks:
        return "No matching content found in this file."
    logger.info("[tools] search_in_file file_id=%s query=%r chunks=%d", file_id, query[:50], len(chunks))
    body = "\n\n---\n\n".join(c["content"] for c in chunks)
    return f"{body}\n\n[{len(chunks)} chunk(s) matched. Use read_file for full file content.]"


async def _search_across_files(db: AsyncSession, conv_id: uuid.UUID, query: str, user_id: int) -> str:
    result = await db.execute(
        select(ConversationFile.file_id).where(ConversationFile.conversation_id == conv_id)
    )
    file_ids = list(result.scalars().all())
    if not file_ids:
        result2 = await db.execute(
            select(FileModel.id).where(FileModel.user_id == user_id, FileModel.upload_status == "ready")
        )
        file_ids = list(result2.scalars().all())
    if not file_ids:
        return "No files available."
    query_emb = await embed(query, input_type="query")
    if not query_emb:
        return "Error: could not embed query (embedding API unavailable)."
    chunks = await retrieve_from_files(db, query_emb, file_ids, top_k=10)
    if not chunks:
        return "No matching content found across attached files."
    logger.info("[tools] search_across_files conv=%s query=%r chunks=%d", conv_id, query[:50], len(chunks))
    body = "\n\n---\n\n".join(c["content"] for c in chunks)
    return f"{body}\n\n[{len(chunks)} chunk(s) matched across {len(file_ids)} file(s). Use read_file for full file content.]"
