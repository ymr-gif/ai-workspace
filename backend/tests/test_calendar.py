"""Calendar tool tests — mocked API, no live Calendar."""
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from llm.tools import ToolContext
from llm.tools.builtin.calendar_tools import _cal_full_gate


class TestCapabilityGating:
    """Calendar tools are gated on capability AND the session intent latch (Q3 Task B
    generalization): connector active AND the session latched on calendar intent. The
    latch is resolved in generate_stream from an embedding cosine; the gate reads flags."""

    def test_injected_when_connector_active_and_latched(self):
        for msg in ("what's on my calendar", "what is the weather today", "", "hi"):
            assert _cal_full_gate(ToolContext(message=msg, calendar_active=True, calendar_latched=True))

    def test_not_injected_before_latch(self):
        # Active but NOT latched → schema withheld even for an explicit calendar ask.
        for msg in ("list events", "book a meeting", "create event", "hi"):
            assert not _cal_full_gate(ToolContext(message=msg, calendar_active=True, calendar_latched=False))

    def test_not_injected_when_connector_inactive(self):
        for msg in ("list events", "book a meeting", "create event"):
            assert not _cal_full_gate(ToolContext(message=msg, calendar_active=False, calendar_latched=True))


@pytest.mark.asyncio
async def test_calendar_create_returns_confirm_sentinel():
    from llm.tools.builtin.calendar_tools import _exec_calendar_create_event
    from llm.tools.registry import CONFIRM_CALENDAR_PREFIX

    ctx = MagicMock()
    ctx.calendar_active = True
    args = {"summary": "Test Event", "start": "2026-06-18T10:00:00", "end": "2026-06-18T11:00:00"}
    result = await _exec_calendar_create_event(args, ctx)
    assert result.startswith(CONFIRM_CALENDAR_PREFIX)
    payload = json.loads(result[len(CONFIRM_CALENDAR_PREFIX):])
    assert payload["op"] == "create"
    assert payload["args"]["summary"] == "Test Event"
    assert "Test Event" in payload["summary"]


@pytest.mark.asyncio
async def test_calendar_update_returns_confirm_sentinel():
    from llm.tools.builtin.calendar_tools import _exec_calendar_update_event
    from llm.tools.registry import CONFIRM_CALENDAR_PREFIX

    ctx = MagicMock()
    ctx.calendar_active = True
    args = {"event_id": "abc123", "summary": "Updated Title"}
    result = await _exec_calendar_update_event(args, ctx)
    assert result.startswith(CONFIRM_CALENDAR_PREFIX)
    payload = json.loads(result[len(CONFIRM_CALENDAR_PREFIX):])
    assert payload["op"] == "update"
    assert payload["args"]["event_id"] == "abc123"


@pytest.mark.asyncio
async def test_calendar_delete_returns_confirm_sentinel():
    from llm.tools.builtin.calendar_tools import _exec_calendar_delete_event
    from llm.tools.registry import CONFIRM_CALENDAR_PREFIX

    ctx = MagicMock()
    ctx.calendar_active = True
    args = {"event_id": "def456"}
    result = await _exec_calendar_delete_event(args, ctx)
    assert result.startswith(CONFIRM_CALENDAR_PREFIX)
    payload = json.loads(result[len(CONFIRM_CALENDAR_PREFIX):])
    assert payload["op"] == "delete"


@pytest.mark.asyncio
async def test_calendar_list_events():
    from llm.tools.calendar import _calendar_list_events

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "items": [
            {"id": "ev1", "summary": "Team Sync", "start": {"dateTime": "2026-06-18T10:00:00"}, "end": {"dateTime": "2026-06-18T11:00:00"}},
            {"id": "ev2", "summary": "Lunch", "start": {"dateTime": "2026-06-18T12:00:00"}, "end": {"dateTime": "2026-06-18T13:00:00"}, "location": "Cafe"},
        ]
    }

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=fake_resp)

    mock_db = AsyncMock()
    cred_ctx = MagicMock()
    cred_ctx.status = "active"
    mock_db.scalar = AsyncMock(return_value=cred_ctx)

    fake_creds = {"access_token": "tok", "refresh_token": "rtok", "expires_at": 9999999999}

    with patch("llm.tools.calendar._load_calendar_creds", AsyncMock(return_value=(cred_ctx, fake_creds))), \
         patch("llm.tools.calendar.llm_client.client", mock_client):
        result = await _calendar_list_events(mock_db, 1)

    assert "Team Sync" in result
    assert "Lunch" in result
    assert "ev1" in result
    assert "Cafe" in result


@pytest.mark.asyncio
async def test_calendar_no_connection():
    from llm.tools.calendar import _calendar_list_events

    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=None)

    with patch("llm.tools.calendar._load_calendar_creds", AsyncMock(return_value=(None, None))):
        result = await _calendar_list_events(mock_db, 1)

    assert "not connected" in result.lower()
