"""The `Tool` abstraction — one self-describing object per tool.

Co-locates everything that used to be scattered across schemas.py / executor.py /
context.py / stream.py. The chat loop never special-cases a tool by name; it reads
these fields generically. Local tools and (future) MCP-wrapped remote tools satisfy
the same contract, which is the seam MCP plugs into.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .context_types import ToolContext

# Pure sync predicate: never do I/O here (resolve flags onto ToolContext first).
InjectFn = Callable[[ToolContext], bool]
# Executes the tool; returns the string the model sees as the tool result.
ExecuteFn = Callable[[dict, ToolContext], Awaitable[str]]


def _never(_ctx: ToolContext) -> bool:
    return False


@dataclass(frozen=True)
class Tool:
    name: str
    schema: dict                      # the {"type":"function", "function":{...}} dict
    execute: ExecuteFn
    should_inject: InjectFn = _never

    requires_reasoning: bool = False  # informational: tool only offered on reasoning model
    is_list_tool: bool = False        # listing tools loop-abort after 1 identical call
    max_identical_calls: int | None = None   # None → MAX_IDENTICAL_CALLS default (3)
    behavioral_rules: str | None = None       # system msg inserted once when this tool is active
    post_call_system_msg: str | None = None   # system msg appended after this tool's result
