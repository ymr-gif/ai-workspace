import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from models import ToolCallLog

from .file_ops import (
    _list_files, _read_file, _write_file, _create_file,
    _append_to_file, _patch_file,
)
from .search import _search_in_file, _search_across_files

logger = logging.getLogger("tools")

ASK_USER_PREFIX = "__ASK_USER__:"


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
        elif name == "query_graph":
            from llm.graph_memory import query_by_term
            term   = args.get("query", "")
            result = (await query_by_term(user_id, term)) or "No entities found for that query."
    except Exception as e:
        logger.warning("[tools] execute_tool failed name=%s err=%s", name, e)
        result = f"Error: {e}"

    try:
        preview = result if result.startswith(ASK_USER_PREFIX) else result[:500]
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
