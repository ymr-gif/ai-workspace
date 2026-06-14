"""File / search / knowledge-graph tools.

All are offered together whenever the conversation has attached files
(`file_ids` present + a DB session) — matching the old
`file_tools = FILE_TOOL_SCHEMAS if (file_ids and db is not None) else []` gate.
"""

from __future__ import annotations

import uuid

from ..base import Tool
from ..context_types import ToolContext
from ..registry import register_tool
from ..schemas import SCHEMA_BY_NAME
from ..file_ops import (
    _list_files, _read_file, _write_file, _create_file,
    _append_to_file, _patch_file,
)
from ..search import _search_in_file, _search_across_files


def _inject(ctx: ToolContext) -> bool:
    return bool(ctx.file_ids) and ctx.db is not None


async def _exec_list_files(args: dict, ctx: ToolContext) -> str:
    return await _list_files(ctx.db, ctx.conv_id, ctx.user_id)


async def _exec_read_file(args: dict, ctx: ToolContext) -> str:
    return await _read_file(ctx.db, ctx.user_id, uuid.UUID(args["file_id"]))


async def _exec_write_file(args: dict, ctx: ToolContext) -> str:
    return await _write_file(ctx.db, ctx.user_id, uuid.UUID(args["file_id"]), args["content"])


async def _exec_create_file(args: dict, ctx: ToolContext) -> str:
    return await _create_file(ctx.db, ctx.user_id, ctx.conv_id, args["name"], args["content"])


async def _exec_append_to_file(args: dict, ctx: ToolContext) -> str:
    return await _append_to_file(ctx.db, ctx.user_id, uuid.UUID(args["file_id"]), args["content"])


async def _exec_patch_file(args: dict, ctx: ToolContext) -> str:
    return await _patch_file(ctx.db, ctx.user_id, uuid.UUID(args["file_id"]), args["old_text"], args["new_text"])


async def _exec_search_in_file(args: dict, ctx: ToolContext) -> str:
    return await _search_in_file(ctx.db, ctx.user_id, uuid.UUID(args["file_id"]), args["query"])


async def _exec_search_across_files(args: dict, ctx: ToolContext) -> str:
    return await _search_across_files(ctx.db, ctx.conv_id, args["query"], ctx.user_id)


async def _exec_query_graph(args: dict, ctx: ToolContext) -> str:
    from llm.graph_memory import query_by_term
    term = args.get("query", "")
    return (await query_by_term(ctx.user_id, term)) or "No entities found for that query."


_EXEC = {
    "list_files": _exec_list_files,
    "read_file": _exec_read_file,
    "write_file": _exec_write_file,
    "create_file": _exec_create_file,
    "append_to_file": _exec_append_to_file,
    "patch_file": _exec_patch_file,
    "search_in_file": _exec_search_in_file,
    "search_across_files": _exec_search_across_files,
    "query_graph": _exec_query_graph,
}

for _name, _fn in _EXEC.items():
    # list_files is a listing tool — abort the loop after a single identical call.
    _is_list = _name == "list_files"
    register_tool(Tool(
        name=_name,
        schema=SCHEMA_BY_NAME[_name],
        execute=_fn,
        should_inject=_inject,
        is_list_tool=_is_list,
        max_identical_calls=1 if _is_list else None,
    ))
