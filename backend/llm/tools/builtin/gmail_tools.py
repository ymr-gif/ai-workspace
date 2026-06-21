from __future__ import annotations

from ..base import Tool
from ..context_types import ToolContext
from ..registry import register_tool
from ..schemas import SCHEMA_BY_NAME

_GMAIL_RULES = (
    "Rules for Gmail tools:\n"
    "- After gmail_list_messages or gmail_search_messages: present the message "
    "previews (subject, sender, date) to the user, then ASK which message(s) to "
    "read — do NOT automatically call gmail_get_message.\n"
    "- When the user specifies a message by its ID or subject, call "
    "gmail_get_message with the message ID.\n"
    "- Only call gmail_get_message when the user explicitly asks to read a "
    "specific message.\n"
    "- Gmail is read-only — you cannot send, delete, or modify messages."
)


def _gmail_full_gate(ctx: ToolContext) -> bool:
    if not ctx.gmail_active:
        return False
    from llm.service.context import _needs_gmail_tools
    return _needs_gmail_tools(ctx.message)


async def _exec_gmail_list_messages(args: dict, ctx: ToolContext) -> str:
    from ..gmail import _gmail_list_messages
    return await _gmail_list_messages(ctx.db, ctx.user_id, args.get("max_results", 20))


async def _exec_gmail_get_message(args: dict, ctx: ToolContext) -> str:
    from ..gmail import _gmail_get_message
    return await _gmail_get_message(ctx.db, ctx.user_id, args["message_id"])


async def _exec_gmail_search_messages(args: dict, ctx: ToolContext) -> str:
    from ..gmail import _gmail_search_messages
    return await _gmail_search_messages(ctx.db, ctx.user_id, args["query"], args.get("max_results", 10))


register_tool(Tool(
    name="gmail_list_messages",
    schema=SCHEMA_BY_NAME["gmail_list_messages"],
    execute=_exec_gmail_list_messages,
    should_inject=_gmail_full_gate,
    is_list_tool=True,
    max_identical_calls=1,
    behavioral_rules=_GMAIL_RULES,
))

register_tool(Tool(
    name="gmail_get_message",
    schema=SCHEMA_BY_NAME["gmail_get_message"],
    execute=_exec_gmail_get_message,
    should_inject=_gmail_full_gate,
    behavioral_rules=_GMAIL_RULES,
))

register_tool(Tool(
    name="gmail_search_messages",
    schema=SCHEMA_BY_NAME["gmail_search_messages"],
    execute=_exec_gmail_search_messages,
    should_inject=_gmail_full_gate,
    is_list_tool=True,
    max_identical_calls=1,
    behavioral_rules=_GMAIL_RULES,
))
