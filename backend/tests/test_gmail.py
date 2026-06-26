"""Gmail tool tests — mocked API, no live Gmail."""
import json
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from llm.tools import ToolContext
from llm.tools.builtin.gmail_tools import _gmail_full_gate


class TestCapabilityGating:
    """Gmail tools are now offered on capability alone (connector active),
    independent of message wording — the model decides when to call them."""

    def test_injected_when_connector_active(self):
        for msg in ("check my email", "what is the weather today", "", "hi"):
            assert _gmail_full_gate(ToolContext(message=msg, gmail_active=True))

    def test_not_injected_when_connector_inactive(self):
        for msg in ("read gmail", "show inbox", "list messages"):
            assert not _gmail_full_gate(ToolContext(message=msg, gmail_active=False))


@pytest.mark.asyncio
async def test_gmail_list_messages():
    user_id = 1
    mock_messages = [
        {"id": "msg1", "threadId": "thread1"},
        {"id": "msg2", "threadId": "thread2"},
    ]
    mock_detail1 = {
        "id": "msg1",
        "snippet": "See you at the meeting",
        "payload": {
            "headers": [
                {"name": "From", "value": "alice@example.com"},
                {"name": "Subject", "value": "Meeting tomorrow"},
                {"name": "Date", "value": "Mon, 1 Jun 2026 10:00:00 +0000"},
            ]
        },
    }
    mock_detail2 = {
        "id": "msg2",
        "snippet": "Here is the report",
        "payload": {
            "headers": [
                {"name": "From", "value": "bob@example.com"},
                {"name": "Subject", "value": "Weekly report"},
                {"name": "Date", "value": "Tue, 2 Jun 2026 14:00:00 +0000"},
            ]
        },
    }

    list_resp = MagicMock()
    list_resp.status_code = 200
    list_resp.json.return_value = {"messages": mock_messages}

    detail_resp1 = MagicMock()
    detail_resp1.status_code = 200
    detail_resp1.json.return_value = mock_detail1

    detail_resp2 = MagicMock()
    detail_resp2.status_code = 200
    detail_resp2.json.return_value = mock_detail2

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=[list_resp, detail_resp1, detail_resp2])

    mock_db = AsyncMock()
    cred_ctx = MagicMock()
    cred_ctx.status = "active"
    mock_db.scalar = AsyncMock(return_value=cred_ctx)

    fake_creds = {"access_token": "tok", "refresh_token": "rtok", "expires_at": 9999999999}

    with patch("llm.tools.gmail._load_credentials", AsyncMock(return_value=(cred_ctx, fake_creds))), \
         patch("llm.tools.gmail.llm_client.client", mock_client):
        from llm.tools.gmail import _gmail_list_messages
        result = await _gmail_list_messages(mock_db, user_id)

    assert "Meeting tomorrow" in result
    assert "Weekly report" in result
    assert "alice@example.com" in result
    assert "bob@example.com" in result
    assert "msg1" in result
    assert "msg2" in result


@pytest.mark.asyncio
async def test_gmail_get_message():
    user_id = 1
    message_id = "msg123"
    mock_message = {
        "id": "msg123",
        "snippet": "Test snippet",
        "payload": {
            "headers": [
                {"name": "From", "value": "charlie@example.com"},
                {"name": "Subject", "value": "Important update"},
                {"name": "Date", "value": "Wed, 3 Jun 2026 09:00:00 +0000"},
            ],
            "body": {
                "data": "VGhpcyBpcyB0aGUgYm9keSB0ZXh0Lg==",  # "This is the body text."
            },
        },
    }

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = mock_message

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=resp)

    mock_db = AsyncMock()
    cred_ctx = MagicMock()
    cred_ctx.status = "active"
    mock_db.scalar = AsyncMock(return_value=cred_ctx)

    fake_creds = {"access_token": "tok", "refresh_token": "rtok", "expires_at": 9999999999}

    with patch("llm.tools.gmail._load_credentials", AsyncMock(return_value=(cred_ctx, fake_creds))), \
         patch("llm.tools.gmail.llm_client.client", mock_client):
        from llm.tools.gmail import _gmail_get_message
        result = await _gmail_get_message(mock_db, user_id, message_id)

    assert "Important update" in result
    assert "charlie@example.com" in result
    assert "This is the body text." in result


@pytest.mark.asyncio
async def test_gmail_search_messages():
    user_id = 1
    mock_results = {"messages": [{"id": "msg99", "threadId": "thread99"}]}
    mock_detail = {
        "id": "msg99",
        "snippet": "Lunch at noon",
        "payload": {
            "headers": [
                {"name": "From", "value": "dave@example.com"},
                {"name": "Subject", "value": "Lunch today"},
                {"name": "Date", "value": "Thu, 4 Jun 2026 12:00:00 +0000"},
            ]
        },
    }

    list_resp = MagicMock()
    list_resp.status_code = 200
    list_resp.json.return_value = mock_results

    detail_resp = MagicMock()
    detail_resp.status_code = 200
    detail_resp.json.return_value = mock_detail

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=[list_resp, detail_resp])

    mock_db = AsyncMock()
    cred_ctx = MagicMock()
    cred_ctx.status = "active"
    mock_db.scalar = AsyncMock(return_value=cred_ctx)

    fake_creds = {"access_token": "tok", "refresh_token": "rtok", "expires_at": 9999999999}

    with patch("llm.tools.gmail._load_credentials", AsyncMock(return_value=(cred_ctx, fake_creds))), \
         patch("llm.tools.gmail.llm_client.client", mock_client):
        from llm.tools.gmail import _gmail_search_messages
        result = await _gmail_search_messages(mock_db, user_id, "lunch")

    assert "Lunch today" in result
    assert "dave@example.com" in result
    assert "lunch" in result.lower()


@pytest.mark.asyncio
async def test_gmail_tool_no_connection():
    user_id = 1
    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=None)

    from llm.tools.gmail import _gmail_list_messages
    result = await _gmail_list_messages(mock_db, user_id)
    assert "not connected" in result.lower()
