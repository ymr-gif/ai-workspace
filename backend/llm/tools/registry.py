"""Tool registry + central execution envelope.

Mirrors `backend/services/integrations/registry.py` (dict + register + getter).
`run_tool` is the ONE place that wraps a tool call: error handling, result
normalization, and `ToolCallLog` auditing — identical to the old `execute_tool`
envelope, so no individual tool re-implements it.

Adding a tool (local or MCP-wrapped) = build a `Tool` and `register_tool(it)`.
"""

from __future__ import annotations

import json
import logging

from models import ToolCallLog

from .base import Tool
from .context_types import ToolContext

logger = logging.getLogger("tools")

# Sentinels the stream loop string-matches to pause for user input / confirmation.
ASK_USER_PREFIX = "__ASK_USER__:"
CONFIRM_WRITE_PREFIX = "__CONFIRM_WRITE_MEMORY__:"
CONFIRM_CALENDAR_PREFIX = "__CONFIRM_CALENDAR_WRITE__:"

TOOL_REGISTRY: dict[str, Tool] = {}


def register_tool(tool: Tool) -> Tool:
    TOOL_REGISTRY[tool.name] = tool
    return tool


def get_tool(name: str) -> Tool | None:
    return TOOL_REGISTRY.get(name)


# Prefilter switch — chooses which capability-available schemas to send the model.
# Call site (generate_stream) never changes; only this function grows when the
# tool count outgrows a single stable prompt prefix.
TOOL_PREFILTER_THRESHOLD = 32  # activate embedding prefilter past this count


def select_tool_schemas(query: str, schemas: list[dict]) -> list[dict]:
    """Return the tool schemas to pass to the model.

    <= threshold: passthrough (all tools). Cheap — a stable, name-sorted prompt
                  prefix lets the KV prefix cache make repeat cost near-zero.
    >  threshold: embedding prefilter (NOT YET BUILT). Embed the query, cosine-
                  match against cached tool-description vectors, pass the top-k.

    Switch is empty by design. Fill the else branch when the tool count grows.
    """
    if len(schemas) <= TOOL_PREFILTER_THRESHOLD:
        return schemas

    # TODO(>32 tools): embedding prefilter
    #   1. embed query (reuse the text embedder)
    #   2. cosine vs cached tool-description vectors
    #   3. return top-k by score
    # Until built, fail safe to passthrough:
    return schemas


async def run_tool(name: str, args: dict, ctx: ToolContext) -> str:
    """Execute a registered tool with the shared error/log envelope."""
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        result: str = f"Unknown tool: {name}"
    else:
        try:
            result = await tool.execute(args, ctx)
        except Exception as e:  # noqa: BLE001 — mirror old execute_tool behavior
            logger.warning("[tools] run_tool failed name=%s err=%s", name, e)
            result = f"Error: {e}"

    if result is None:
        result = "ok"
    elif not isinstance(result, str):
        result = json.dumps(result)

    if ctx.db is not None:
        try:
            preview = result if (result.startswith(ASK_USER_PREFIX) or result.startswith(CONFIRM_WRITE_PREFIX) or result.startswith(CONFIRM_CALENDAR_PREFIX)) else result[:500]
            ctx.db.add(ToolCallLog(
                user_id=ctx.user_id,
                conversation_id=ctx.conv_id,
                tool_name=name,
                args=args,
                result_preview=preview,
            ))
            await ctx.db.flush()
        except Exception:
            await ctx.db.rollback()

    return result
