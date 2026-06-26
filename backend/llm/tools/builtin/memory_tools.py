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


# write_memory: capability gate only — reasoning model + a DB session. The model
# decides when to persist a fact from the schema description.
def _inject_write_memory(ctx: ToolContext) -> bool:
    return ctx.db is not None and ctx.is_reasoning


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
