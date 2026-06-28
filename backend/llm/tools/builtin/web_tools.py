"""web_search and fetch_url — conditionally injected, lazy-imported impls.

web_search: capability gate only — offered whenever WEB_SEARCH_ENABLED (carried
            on the context). The model decides when to call it from the schema.
fetch_url:  needs a URL in the message (nothing to fetch otherwise).
"""

from __future__ import annotations

import re

from ..base import Tool
from ..context_types import ToolContext
from ..registry import register_tool
from ..schemas import SCHEMA_BY_NAME

_URL_RE = re.compile(r'https?://')


def _inject_web_search(ctx: ToolContext) -> bool:
    # Capability gate only — offered whenever a search provider is configured.
    return ctx.web_search_enabled


async def _exec_web_search(args: dict, ctx: ToolContext) -> str:
    query = args.get("query", "").strip()
    if not query:
        return "Error: query must not be empty."
    from llm.tools.web_search import run_web_search
    results = await run_web_search(query)
    lines = [f"[{i+1}] {r['title']}\n{r['url']}\n{r['snippet']}" for i, r in enumerate(results)]
    return "\n\n".join(lines) if lines else "No results found."


def _inject_fetch_url(ctx: ToolContext) -> bool:
    if _URL_RE.search(ctx.message):
        return True
    for turn in (ctx.history or [])[-6:]:
        if isinstance(turn.get("content"), str) and _URL_RE.search(turn["content"]):
            return True
    return False


async def _exec_fetch_url(args: dict, ctx: ToolContext) -> str:
    from llm.tools.fetch_url import run_fetch_url
    return await run_fetch_url(args.get("url", ""))


register_tool(Tool(
    name="web_search",
    schema=SCHEMA_BY_NAME["web_search"],
    execute=_exec_web_search,
    should_inject=_inject_web_search,
))

register_tool(Tool(
    name="fetch_url",
    schema=SCHEMA_BY_NAME["fetch_url"],
    execute=_exec_fetch_url,
    should_inject=_inject_fetch_url,
))
