from __future__ import annotations

import json

from ..base import Tool
from ..context_types import ToolContext
from ..registry import register_tool, CONFIRM_CALENDAR_PREFIX
from ..schemas import SCHEMA_BY_NAME

_CALENDAR_RULES = (
    "Rules for Google Calendar tools:\n"
    "- After calendar_list_events: present the events to the user with their times. "
    "If the user wants details on a specific event, call calendar_get_event with its ID.\n"
    "- For calendar_search_events: present matching events. "
    "If the user wants details, call calendar_get_event with its ID.\n"
    "- For create/update/delete operations: present a clear summary of what will happen. "
    "The system will show a confirmation card to the user before the change is made.\n"
    "- Do NOT call calendar_list_events immediately before calendar_get_event — "
    "if the user names or references a specific event, use its ID directly."
)


def _cal_full_gate(ctx: ToolContext) -> bool:
    if not ctx.calendar_active:
        return False
    from llm.service.context import _needs_calendar_tools
    return _needs_calendar_tools(ctx.message)


async def _exec_calendar_list_events(args: dict, ctx: ToolContext) -> str:
    from ..calendar import _calendar_list_events
    return await _calendar_list_events(
        ctx.db,
        ctx.user_id,
        time_min=args.get("time_min"),
        time_max=args.get("time_max"),
        max_results=args.get("max_results", 20),
    )


async def _exec_calendar_get_event(args: dict, ctx: ToolContext) -> str:
    from ..calendar import _calendar_get_event
    return await _calendar_get_event(ctx.db, ctx.user_id, args["event_id"])


async def _exec_calendar_search_events(args: dict, ctx: ToolContext) -> str:
    from ..calendar import _calendar_search_events
    return await _calendar_search_events(ctx.db, ctx.user_id, args["query"])


async def _exec_calendar_create_event(args: dict, ctx: ToolContext) -> str:
    summary = args.get("summary", "")
    start = args.get("start", "")
    end = args.get("end", "")
    preview = f"Create event: {summary} ({start} → {end})"
    return f"{CONFIRM_CALENDAR_PREFIX}{json.dumps({'op': 'create', 'args': args, 'summary': preview})}"


async def _exec_calendar_update_event(args: dict, ctx: ToolContext) -> str:
    summary = args.get("summary", "(no title change)")
    preview = f"Update event {args['event_id']}: {summary}"
    return f"{CONFIRM_CALENDAR_PREFIX}{json.dumps({'op': 'update', 'args': args, 'summary': preview})}"


async def _exec_calendar_delete_event(args: dict, ctx: ToolContext) -> str:
    preview = f"Delete event: {args['event_id']}"
    return f"{CONFIRM_CALENDAR_PREFIX}{json.dumps({'op': 'delete', 'args': args, 'summary': preview})}"


register_tool(Tool(
    name="calendar_list_events",
    schema=SCHEMA_BY_NAME["calendar_list_events"],
    execute=_exec_calendar_list_events,
    should_inject=_cal_full_gate,
    is_list_tool=True,
    max_identical_calls=1,
    behavioral_rules=_CALENDAR_RULES,
))

register_tool(Tool(
    name="calendar_get_event",
    schema=SCHEMA_BY_NAME["calendar_get_event"],
    execute=_exec_calendar_get_event,
    should_inject=_cal_full_gate,
    behavioral_rules=_CALENDAR_RULES,
))

register_tool(Tool(
    name="calendar_search_events",
    schema=SCHEMA_BY_NAME["calendar_search_events"],
    execute=_exec_calendar_search_events,
    should_inject=_cal_full_gate,
    is_list_tool=True,
    max_identical_calls=1,
    behavioral_rules=_CALENDAR_RULES,
))

register_tool(Tool(
    name="calendar_create_event",
    schema=SCHEMA_BY_NAME["calendar_create_event"],
    execute=_exec_calendar_create_event,
    should_inject=_cal_full_gate,
    requires_reasoning=True,
    behavioral_rules=_CALENDAR_RULES,
))

register_tool(Tool(
    name="calendar_update_event",
    schema=SCHEMA_BY_NAME["calendar_update_event"],
    execute=_exec_calendar_update_event,
    should_inject=_cal_full_gate,
    requires_reasoning=True,
    behavioral_rules=_CALENDAR_RULES,
))

register_tool(Tool(
    name="calendar_delete_event",
    schema=SCHEMA_BY_NAME["calendar_delete_event"],
    execute=_exec_calendar_delete_event,
    should_inject=_cal_full_gate,
    requires_reasoning=True,
    behavioral_rules=_CALENDAR_RULES,
))
