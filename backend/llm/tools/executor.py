"""Back-compat entry point for executing a tool by name.

All tools now live in the registry (`builtin/` modules register them). This is a
thin shim that builds a `ToolContext` and dispatches through `run_tool`, which
owns the error/result/logging envelope. `ASK_USER_PREFIX` / `CONFIRM_WRITE_PREFIX`
are re-exported here for existing importers.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from .registry import run_tool, ASK_USER_PREFIX, CONFIRM_WRITE_PREFIX  # noqa: F401 (re-exported)
from .context_types import ToolContext


async def execute_tool(
    name:    str,
    args:    dict,
    db:      AsyncSession,
    user_id: int,
    conv_id: uuid.UUID,
) -> str:
    return await run_tool(name, args, ToolContext(db=db, user_id=user_id, conv_id=conv_id))
