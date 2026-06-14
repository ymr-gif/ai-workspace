"""Uniform context passed to every tool's `should_inject` and `execute`.

Replaces the ad-hoc per-tool argument subsets that used to be threaded through
`execute_tool` / the `generate_stream` injection blocks. A single object means a
new tool pulls only what it needs, and the same shape works for an MCP adapter.

Async-resolved flags (`drive_active`, `drive_cache_active`) are computed ONCE
before the injection loop and stashed here so `should_inject` stays a pure,
synchronous, side-effect-free predicate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolContext:
    message: str = ""
    history: list[dict] = field(default_factory=list)

    db: Any | None = None            # AsyncSession (kept loose to avoid import cost)
    user_id: int | None = None
    conv_id: uuid.UUID | None = None

    file_ids: tuple = ()
    is_reasoning: bool = False
    web_search_enabled: bool = False
    use_redis: bool = False

    # resolved once before the injection loop (async I/O lives there, not here)
    drive_active: bool = False
    drive_cache_active: bool = False
