import asyncio
import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ConversationFile, File as FileModel, FileChunk
from services.processor import process_file_async
from storage.storage_manager import StorageManager
from llm.embeddings import embed
from llm.retriever import retrieve_from_files

logger = logging.getLogger("tools")

MAX_FILE_READ = 100_000

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files attached to the current conversation with their IDs.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full text content of a file by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "UUID of the file to read."},
                },
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Overwrite a file with new content. You MUST call this to save any changes — outputting text alone does not modify the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "UUID of the file to update."},
                    "content": {"type": "string", "description": "New full text content of the file."},
                },
                "required": ["file_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new text file and attach it to the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":    {"type": "string", "description": "Filename (e.g. notes.txt)."},
                    "content": {"type": "string", "description": "Text content of the new file."},
                },
                "required": ["name", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_file",
            "description": "Append text to the end of a file without touching existing content. Use this instead of write_file when adding new content (paragraphs, sections, notes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "UUID of the file to append to."},
                    "content": {"type": "string", "description": "Text to append at the end of the file."},
                },
                "required": ["file_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Replace a specific passage in a file with new text. Safer than write_file — only changes the matched section, preserves everything else. Use when editing or rewriting a specific part.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id":  {"type": "string", "description": "UUID of the file to patch."},
                    "old_text": {"type": "string", "description": "Exact text to find and replace (must match the file exactly)."},
                    "new_text": {"type": "string", "description": "Replacement text."},
                },
                "required": ["file_id", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_file",
            "description": "Semantic search within a specific file. Returns top matching passages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "UUID of the file to search."},
                    "query":   {"type": "string", "description": "Search query."},
                },
                "required": ["file_id", "query"],
            },
        },
    },
]


async def execute_tool(
    name:    str,
    args:    dict,
    db:      AsyncSession,
    user_id: int,
    conv_id: uuid.UUID,
) -> str:
    try:
        if name == "list_files":
            return await _list_files(db, conv_id)
        if name == "read_file":
            return await _read_file(db, user_id, uuid.UUID(args["file_id"]))
        if name == "write_file":
            return await _write_file(db, user_id, uuid.UUID(args["file_id"]), args["content"])
        if name == "create_file":
            return await _create_file(db, user_id, conv_id, args["name"], args["content"])
        if name == "append_to_file":
            return await _append_to_file(db, user_id, uuid.UUID(args["file_id"]), args["content"])
        if name == "patch_file":
            return await _patch_file(db, user_id, uuid.UUID(args["file_id"]), args["old_text"], args["new_text"])
        if name == "search_in_file":
            return await _search_in_file(db, user_id, uuid.UUID(args["file_id"]), args["query"])
        return f"Unknown tool: {name}"
    except Exception as e:
        logger.warning("[tools] execute_tool failed name=%s err=%s", name, e)
        return f"Error: {e}"


async def _list_files(db: AsyncSession, conv_id: uuid.UUID) -> str:
    result = await db.execute(
        select(FileModel.id, FileModel.filename, FileModel.size_bytes, FileModel.upload_status)
        .join(ConversationFile, ConversationFile.file_id == FileModel.id)
        .where(ConversationFile.conversation_id == conv_id)
    )
    rows = result.all()
    if not rows:
        return "No files attached to this conversation."
    lines = [
        f"- {r.filename} (id={r.id}, size={r.size_bytes} bytes, status={r.upload_status})"
        for r in rows
    ]
    logger.info("[tools] list_files conv=%s count=%d", conv_id, len(rows))
    return "\n".join(lines)


async def _read_file(db: AsyncSession, user_id: int, file_id: uuid.UUID) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    try:
        with open(f.storage_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read(MAX_FILE_READ)
        truncated = len(content) == MAX_FILE_READ
        logger.info("[tools] read_file file_id=%s chars=%d truncated=%s", file_id, len(content), truncated)
        if truncated:
            content += f"\n\n[File truncated at {MAX_FILE_READ:,} characters]"
        return content
    except Exception as e:
        logger.warning("[tools] read_file failed file_id=%s err=%s", file_id, e)
        return f"Error reading file: {e}"


async def _write_file(db: AsyncSession, user_id: int, file_id: uuid.UUID, content: str) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    try:
        with open(f.storage_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        await db.execute(delete(FileChunk).where(FileChunk.file_id == file_id))
        f.upload_status = "uploaded"
        await db.commit()
        asyncio.create_task(process_file_async(file_id, f.storage_path, f.mime_type))
        logger.info("[tools] write_file file_id=%s chars=%d reprocessing", file_id, len(content))
        return f"File updated ({len(content):,} chars). Re-embedding in background."
    except Exception as e:
        logger.warning("[tools] write_file failed file_id=%s err=%s", file_id, e)
        return f"Error writing file: {e}"


async def _create_file(
    db:      AsyncSession,
    user_id: int,
    conv_id: uuid.UUID,
    name:    str,
    content: str,
) -> str:
    storage = StorageManager()
    try:
        storage_path, size_bytes = await storage.save_text(content, name[:80])
        f = FileModel(
            user_id       = user_id,
            filename      = name[:255],
            mime_type     = "text/plain",
            size_bytes    = size_bytes,
            storage_path  = storage_path,
            upload_status = "uploaded",
        )
        db.add(f)
        await db.flush()
        db.add(ConversationFile(conversation_id=conv_id, file_id=f.id))
        await db.commit()
        asyncio.create_task(process_file_async(f.id, storage_path, "text/plain"))
        logger.info("[tools] create_file file_id=%s name=%s", f.id, name)
        return f"File '{name}' created and attached to conversation (id={f.id}). Processing in background."
    except Exception as e:
        logger.warning("[tools] create_file failed name=%s err=%s", name, e)
        return f"Error creating file: {e}"


async def _append_to_file(db: AsyncSession, user_id: int, file_id: uuid.UUID, content: str) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    try:
        with open(f.storage_path, "a", encoding="utf-8") as fh:
            fh.write(("\n\n" if content and not content.startswith("\n") else "") + content)
        await db.execute(delete(FileChunk).where(FileChunk.file_id == file_id))
        f.upload_status = "uploaded"
        await db.commit()
        asyncio.create_task(process_file_async(file_id, f.storage_path, f.mime_type))
        logger.info("[tools] append_to_file file_id=%s chars=%d reprocessing", file_id, len(content))
        return f"Appended {len(content):,} chars to file. Re-embedding in background."
    except Exception as e:
        logger.warning("[tools] append_to_file failed file_id=%s err=%s", file_id, e)
        return f"Error appending to file: {e}"


async def _patch_file(
    db:       AsyncSession,
    user_id:  int,
    file_id:  uuid.UUID,
    old_text: str,
    new_text: str,
) -> str:
    f = await db.get(FileModel, file_id)
    if not f or f.user_id != user_id:
        return "Error: file not found or access denied."
    try:
        with open(f.storage_path, "r", encoding="utf-8", errors="replace") as fh:
            current = fh.read()
        if old_text not in current:
            return "Error: old_text not found in file. Use read_file to get the exact text, then retry."
        updated = current.replace(old_text, new_text, 1)
        with open(f.storage_path, "w", encoding="utf-8") as fh:
            fh.write(updated)
        await db.execute(delete(FileChunk).where(FileChunk.file_id == file_id))
        f.upload_status = "uploaded"
        await db.commit()
        asyncio.create_task(process_file_async(file_id, f.storage_path, f.mime_type))
        logger.info("[tools] patch_file file_id=%s old_len=%d new_len=%d", file_id, len(old_text), len(new_text))
        return f"Patched: replaced {len(old_text):,} chars with {len(new_text):,} chars. Re-embedding in background."
    except Exception as e:
        logger.warning("[tools] patch_file failed file_id=%s err=%s", file_id, e)
        return f"Error patching file: {e}"


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
    return "\n\n---\n\n".join(chunks)
