"""Google Drive tools — behavioral rules and post-listing stop message,
co-located here.

Gate: capability only — all three Drive tools are offered whenever the Drive
connector is connected (`ctx.drive_active`). The model decides which to call
from the schema descriptions; the behavioral rules below steer the list→ask→read
flow. (Keyword/cache pre-filtering was removed in favor of native function
calling.)

The `_drive_*` impls stay in `llm/tools/drive.py` (unchanged path — tests patch them).
"""

from __future__ import annotations

from ..base import Tool
from ..context_types import ToolContext
from ..registry import register_tool
from ..schemas import SCHEMA_BY_NAME

_DRIVE_RULES = (
    "Rules for Google Drive tools:\n"
    "- After drive_list_files: present the file names and types to the user. "
    "Note any marked as [unreadable]. Then ASK the user which file(s) to open — "
    "do NOT automatically call drive_read_file on any file.\n"
    "- When the user names a file to read or open, call drive_read_file directly with that "
    "file NAME (the system resolves it to an ID). If files were already listed or searched "
    "earlier in this conversation, do NOT call drive_list_files again just to get the ID.\n"
    "- Only call drive_read_file when the user explicitly names or requests a specific file.\n"
    "- If drive_read_file returns an error or [unreadable], tell the user and stop — do not retry.\n"
    "- Do not call drive_read_file on files the user has not asked for."
)

_POST_LISTING = (
    "You have the Drive file listing above. "
    "Respond NOW in plain text: present the file names and types to the user. "
    "Note any [unreadable] files. Ask which file(s) they want opened. "
    "Do NOT call any tool. Do NOT call drive_list_files again."
)


def _drive_gate(ctx: ToolContext) -> bool:
    # Capability gate only — offered whenever the Drive connector is active.
    return ctx.drive_active


async def _exec_drive_list_files(args: dict, ctx: ToolContext) -> str:
    from ..drive import _drive_list_files
    return await _drive_list_files(ctx.db, ctx.user_id, ctx.conv_id, args.get("query"))


async def _exec_drive_read_file(args: dict, ctx: ToolContext) -> str:
    from ..drive import _drive_read_file
    return await _drive_read_file(ctx.db, ctx.user_id, ctx.conv_id, args["file_id"])


async def _exec_drive_search(args: dict, ctx: ToolContext) -> str:
    from ..drive import _drive_search
    return await _drive_search(ctx.db, ctx.user_id, ctx.conv_id, args["query"])


register_tool(Tool(
    name="drive_list_files",
    schema=SCHEMA_BY_NAME["drive_list_files"],
    execute=_exec_drive_list_files,
    should_inject=_drive_gate,
    is_list_tool=True,
    max_identical_calls=1,
    behavioral_rules=_DRIVE_RULES,
    post_call_system_msg=_POST_LISTING,
))

register_tool(Tool(
    name="drive_read_file",
    schema=SCHEMA_BY_NAME["drive_read_file"],
    execute=_exec_drive_read_file,
    should_inject=_drive_gate,
    behavioral_rules=_DRIVE_RULES,
))

register_tool(Tool(
    name="drive_search",
    schema=SCHEMA_BY_NAME["drive_search"],
    execute=_exec_drive_search,
    should_inject=_drive_gate,
    is_list_tool=True,
    max_identical_calls=1,
    behavioral_rules=_DRIVE_RULES,
    post_call_system_msg=_POST_LISTING,
))
