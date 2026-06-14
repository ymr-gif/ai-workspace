"""web_search and fetch_url — conditionally injected, lazy-imported impls.

web_search: needs WEB_SEARCH_ENABLED (carried on the context) + a keyword match.
fetch_url:  needs a URL in the message.
"""

from __future__ import annotations

import re

from ..base import Tool
from ..context_types import ToolContext
from ..registry import register_tool
from ..schemas import SCHEMA_BY_NAME

_URL_RE = re.compile(r'https?://')


def _inject_web_search(ctx: ToolContext) -> bool:
    if not ctx.web_search_enabled:
        return False
    from llm.service.context import _needs_web_search
    return _needs_web_search(ctx.message)


async def _exec_web_search(args: dict, ctx: ToolContext) -> str:
    from llm.tools.web_search import run_web_search
    results = await run_web_search(args.get("query", ""))
    lines = [f"[{i+1}] {r['title']}\n{r['url']}\n{r['snippet']}" for i, r in enumerate(results)]
    return "\n\n".join(lines) if lines else "No results found."


def _inject_fetch_url(ctx: ToolContext) -> bool:
    return bool(_URL_RE.search(ctx.message))


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
