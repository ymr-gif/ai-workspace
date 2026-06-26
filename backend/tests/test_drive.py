"""Drive tool tests — mocked API, no live Drive."""
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
from llm.tools.builtin.drive_tools import _drive_gate


class TestCapabilityGating:
    """Drive tools are now offered on capability alone (connector active),
    independent of message wording — the model decides when to call them."""

    def test_injected_when_connector_active(self):
        # Active regardless of wording — even a message with no Drive keyword.
        for msg in ("check my drive", "what is the weather today", "", "hello"):
            assert _drive_gate(ToolContext(message=msg, drive_active=True))

    def test_not_injected_when_connector_inactive(self):
        # Inactive regardless of wording — even an explicit Drive request.
        for msg in ("list my google drive files", "open gdrive", "show sheets"):
            assert not _drive_gate(ToolContext(message=msg, drive_active=False))


@pytest.mark.asyncio
async def test_drive_list_files_caches_listing():
    conv_id = uuid.uuid4()
    user_id = 1
    mock_files = [
        {"id": "abc123", "name": "test.txt", "mimeType": "text/plain", "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "def456", "name": "data.csv", "mimeType": "text/csv", "modifiedTime": "2026-01-02T00:00:00Z"},
    ]

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"files": mock_files, "nextPageToken": None}

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=fake_resp)

    mock_db = AsyncMock()
    cred_ctx = MagicMock()
    cred_ctx.status = "active"
    mock_db.scalar = AsyncMock(return_value=cred_ctx)

    fake_creds = {"access_token": "tok", "refresh_token": "rtok", "expires_at": 9999999999}

    with patch("llm.tools.drive.USE_REDIS", False), \
         patch("llm.tools.drive._load_credentials", AsyncMock(return_value=(cred_ctx, fake_creds))), \
         patch("llm.tools.drive.llm_client.client", mock_client):
        from llm.tools.drive import _drive_list_files
        result = await _drive_list_files(mock_db, user_id, conv_id)

    assert "test.txt" in result
    assert "data.csv" in result
    assert "id=abc123" in result
    assert "id=def456" in result
    assert "[2 file(s) total" in result


@pytest.mark.asyncio
async def test_drive_read_file_resolves_name_from_cache():
    conv_id = uuid.uuid4()
    user_id = 1
    file_id = "abc123"
    file_name = "test.txt"
    file_content = "Hello world"
    cached_listing = {"test.txt": json.dumps({"id": "abc123", "mimeType": "text/plain", "modifiedTime": "2026-01-01T00:00:00Z"})}

    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=cached_listing["test.txt"])

    meta_resp = MagicMock()
    meta_resp.status_code = 200
    meta_resp.json.return_value = {"mimeType": "text/plain", "name": file_name}

    content_resp = MagicMock()
    content_resp.status_code = 200
    content_resp.text = file_content

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=[meta_resp, content_resp])

    mock_db = AsyncMock()
    cred_ctx = MagicMock()
    cred_ctx.status = "active"
    mock_db.scalar = AsyncMock(return_value=cred_ctx)

    fake_creds = {"access_token": "tok", "refresh_token": "rtok", "expires_at": 9999999999}

    with patch("llm.tools.drive.USE_REDIS", True), \
         patch("llm.tools.drive._load_credentials", AsyncMock(return_value=(cred_ctx, fake_creds))), \
         patch("llm.tools.drive.llm_client.client", mock_client), \
         patch("core.redis_client.get_redis", MagicMock(return_value=mock_redis)):
        from llm.tools.drive import _drive_read_file
        result = await _drive_read_file(mock_db, user_id, conv_id, file_name)

    assert "--- test.txt ---" in result
    assert "Hello world" in result


@pytest.mark.asyncio
async def test_drive_read_file_passes_id_directly():
    conv_id = uuid.uuid4()
    user_id = 1
    file_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
    file_content = "Direct ID content"

    meta_resp = MagicMock()
    meta_resp.status_code = 200
    meta_resp.json.return_value = {"mimeType": "text/plain", "name": "doc.txt"}

    content_resp = MagicMock()
    content_resp.status_code = 200
    content_resp.text = file_content

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=[meta_resp, content_resp])

    mock_db = AsyncMock()
    cred_ctx = MagicMock()
    cred_ctx.status = "active"
    mock_db.scalar = AsyncMock(return_value=cred_ctx)

    fake_creds = {"access_token": "tok", "refresh_token": "rtok", "expires_at": 9999999999}

    with patch("llm.tools.drive.USE_REDIS", True), \
         patch("llm.tools.drive._load_credentials", AsyncMock(return_value=(cred_ctx, fake_creds))), \
         patch("llm.tools.drive.llm_client.client", mock_client):
        from llm.tools.drive import _drive_read_file
        result = await _drive_read_file(mock_db, user_id, conv_id, file_id)

    assert "Direct ID content" in result


@pytest.mark.asyncio
async def test_drive_search_caches_listing():
    conv_id = uuid.uuid4()
    user_id = 1
    mock_files = [
        {"id": "xyz789", "name": "notes.txt", "mimeType": "text/plain", "modifiedTime": "2026-03-01T00:00:00Z"},
    ]

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"files": mock_files}

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=fake_resp)

    mock_db = AsyncMock()
    cred_ctx = MagicMock()
    cred_ctx.status = "active"
    mock_db.scalar = AsyncMock(return_value=cred_ctx)

    fake_creds = {"access_token": "tok", "refresh_token": "rtok", "expires_at": 9999999999}

    mock_redis = AsyncMock()

    with patch("llm.tools.drive.USE_REDIS", True), \
         patch("llm.tools.drive._load_credentials", AsyncMock(return_value=(cred_ctx, fake_creds))), \
         patch("llm.tools.drive.llm_client.client", mock_client), \
         patch("core.redis_client.get_redis", MagicMock(return_value=mock_redis)):
        from llm.tools.drive import _drive_search
        result = await _drive_search(mock_db, user_id, conv_id, "notes")

    assert "notes.txt" in result
    assert "id=xyz789" in result


@pytest.mark.asyncio
async def test_drive_tool_no_connection():
    conv_id = uuid.uuid4()
    user_id = 1
    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=None)

    from llm.tools.drive import _drive_list_files
    result = await _drive_list_files(mock_db, user_id, conv_id)
    assert "not connected" in result.lower()
