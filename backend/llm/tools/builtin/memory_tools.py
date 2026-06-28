"""ask_user and write_memory — the two tools whose result is a magic prefix the
stream loop matches to pause for user input / confirmation.

Gating predicates are imported lazily inside `should_inject` to avoid an import
cycle (llm.service.__init__ → stream → llm.tools → here → llm.service.context).
"""

from __future__ import annotations

from ..base import Tool
from ..context_types import ToolContext
from ..registry import register_tool, ASK_USER_PREFIX, CONFIRM_WRITE_PREFIX
from ..schemas import SCHEMA_BY_NAME


# ask_user is part of the file toolset — offered whenever files are attached.
def _inject_ask_user(ctx: ToolContext) -> bool:
    return bool(ctx.file_ids) and ctx.db is not None


async def _exec_ask_user(args: dict, ctx: ToolContext) -> str:
    return f"{ASK_USER_PREFIX}{args.get('question', '')}"


# write_memory: reasoning model + DB session + EXPLICIT memory-write intent in the
# current message. Capability-only (db + is_reasoning) over-fired: on any trivial turn
# that happened to land on the 70B, the tool-eager model called write_memory to store a
# junk "fact" (e.g. "user is saying hello") and — because the confirm sentinel pauses the
# loop — left an EMPTY reply (BUGS.md, conv a863dcbf). The gate now also requires
# `_needs_memory_tool(message)` (the same deterministic "remember"/"memorize" keyword
# signal that routes memory turns to the 70B), so greetings/questions/coding never inject
# write_memory. Embedding-cosine memory-intent was measured too weak to separate (greetings
# ~0.58 ≈ real memory statements; "summarize this" 0.75), so it is NOT used here. Implicit
# preferences are still captured by the background memory-extraction pipeline
# (summarizer/memory.py) — write_memory is only the explicit, immediate confirm-card path.
def _inject_write_memory(ctx: ToolContext) -> bool:
    if not (ctx.db is not None and ctx.is_reasoning):
        return False
    from llm.service.context import _needs_memory_tool  # lazy: avoid import cycle
    return _needs_memory_tool(ctx.message)


async def _exec_write_memory(args: dict, ctx: ToolContext) -> str:
    return f"{CONFIRM_WRITE_PREFIX}{args.get('fact', '')}"


register_tool(Tool(
    name="ask_user",
    schema=SCHEMA_BY_NAME["ask_user"],
    execute=_exec_ask_user,
    should_inject=_inject_ask_user,
))

register_tool(Tool(
    name="write_memory",
    schema=SCHEMA_BY_NAME["write_memory"],
    execute=_exec_write_memory,
    should_inject=_inject_write_memory,
    requires_reasoning=True,
))
