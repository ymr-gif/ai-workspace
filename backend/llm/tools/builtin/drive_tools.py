"""Google Drive tools — behavioral rules and post-listing stop message,
co-located here.

Gate: capability AND session intent latch (Q3 Task B). All three Drive tools are
offered only when the Drive connector is connected (`ctx.drive_active`) AND the
session has latched on genuine Drive intent (`ctx.drive_latched`). Pre-latch the
schema is absent, so the model cannot fire a Drive tool on a greeting; post-latch
the model picks which to call from the schema descriptions and the behavioral
rules below steer the list→ask→read flow. (Keyword/cache pre-filtering was removed
in favor of native function calling; the latch is an embedding-cosine signal, not
a keyword match — see `llm/tools/drive_intent.py`.)

The `_drive_*` impls stay in `llm/tools/drive.py` (unchanged path — tests patch them).
"""

from __future__ import annotations

from ..base import Tool
from ..context_types import ToolContext
from ..registry import register_tool
from ..schemas import SCHEMA_BY_NAME

_DRIVE_RULES = (
    "## Google Drive access\n"
    "\n"
    "You have Google Drive tools available this session. Having access does "
    "not mean you should use it. On most turns you should not.\n"
    "\n"
    "Call a Drive tool ONLY when the user's CURRENT message refers to their "
    "own files, documents, folders, or Drive contents — explicitly or by "
    "clear implication (asking what they have, to open or find a document, "
    "to look something up in their files).\n"
    "\n"
    "Do NOT call any Drive tool for:\n"
    "- greetings, small talk, or acknowledgements (\"hi\", \"hello?\", \"thanks\")\n"
    "- general questions you can answer directly\n"
    "- coding help, explanations, or discussion\n"
    "- any turn where the user has not pointed at their own files\n"
    "\n"
    "Base the decision on the user's CURRENT message only. A previous file "
    "listing in the conversation is not a reason to call again.\n"
    "\n"
    "When unsure whether a turn needs Drive, do not call it — answer "
    "directly. A wrong file listing is worse than a missing one; the user "
    "can always ask.\n"
    "\n"
    "When you DO call drive_list_files and results return, present the file "
    "names concisely and stop."
)

_POST_LISTING = (
    "You have the Drive file listing above. "
    "Respond NOW in plain text: present the file names and types to the user. "
    "Note any [unreadable] files. Ask which file(s) they want opened. "
    "Do NOT call any tool. Do NOT call drive_list_files again."
)


def _drive_gate(ctx: ToolContext) -> bool:
    # Capability AND intent latch (Q3 Task B). Connector active is necessary but
    # not sufficient: the Drive schemas (and _DRIVE_RULES, which rides on this same
    # injection) only enter context once genuine Drive intent has latched the
    # session. Pre-latch the schema is absent, so the model *cannot* spuriously
    # call drive_list_files on a greeting. Post-latch, _DRIVE_RULES covers the
    # trivial-turn case. The latch is resolved once per turn in generate_stream.
    return ctx.drive_active and ctx.drive_latched


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
