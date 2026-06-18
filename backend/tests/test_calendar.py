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

from llm.service.context import _needs_calendar_tools


class TestKeywordGating:
    def test_calendar_noun_action_pair(self):
        assert _needs_calendar_tools("what's on my calendar")
        assert _needs_calendar_tools("list events")
        assert _needs_calendar_tools("show meetings")
        assert _needs_calendar_tools("check my schedule")
        assert _needs_calendar_tools("book a meeting")
        assert _needs_calendar_tools("create event")
        assert _needs_calendar_tools("add appointment")
        assert _needs_calendar_tools("reschedule meeting")
        assert _needs_calendar_tools("cancel event")
        assert _needs_calendar_tools("find agenda")
        assert _needs_calendar_tools("when is my next event")
        assert _needs_calendar_tools("check availability")
        assert _needs_calendar_tools("list my gcal events")
        assert _needs_calendar_tools("show my cal")

    def test_noun_only_no_match(self):
        assert not _needs_calendar_tools("my calendar")
        assert not _needs_calendar_tools("a meeting")
        assert not _needs_calendar_tools("the event")
        assert not _needs_calendar_tools("appointment reminder")
        assert not _needs_calendar_tools("free time is good")

    def test_action_only_no_match(self):
        assert not _needs_calendar_tools("list my files")
        assert not _needs_calendar_tools("show me")
        assert not _needs_calendar_tools("create a document")
        assert not _needs_calendar_tools("search google")

    def test_no_false_positive_calendar(self):
        assert not _needs_calendar_tools("i have a calendar in my room")
        assert not _needs_calendar_tools("the event was cancelled")
        assert not _needs_calendar_tools("meeting adjourned")

    def test_empty_message(self):
        assert not _needs_calendar_tools("")

    def test_unrelated_message(self):
        assert not _needs_calendar_tools("what is the weather today")
        assert not _needs_calendar_tools("read my drive file")

    def test_apostrophe_stripping(self):
        assert _needs_calendar_tools("what's my calendar")
        assert _needs_calendar_tools("what's on my schedule")


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
