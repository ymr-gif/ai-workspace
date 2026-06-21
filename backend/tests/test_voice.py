"""Unit tests for Voice STT (Phase 1a) — run with: pytest backend/tests/test_voice.py -v"""
import os
import sys
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY",  "test-key")
os.environ.setdefault("DATABASE_URL",    "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret")
os.environ.setdefault("VOICE_ENABLED",  "true")

import config
config.VOICE_ENABLED = True

from api.transcribe import router as transcribe_router
from auth.security import get_current_user
from models import User

fake_user = User(id=1, username="testuser", role="user", is_active=True)

async def _fake_user():
    return fake_user


def _make_client(with_auth: bool = True):
    app = FastAPI()
    app.include_router(transcribe_router, prefix="/api")
    if with_auth:
        app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


# ── transcribe_audio unit test ────────────────────────────────────────────────

from services.transcribe import transcribe_audio, STUB_PLACEHOLDER

@pytest.mark.anyio
async def test_transcribe_audio_stub_returns_placeholder():
    result = await transcribe_audio(b"fake audio data", "audio/webm")
    assert result == STUB_PLACEHOLDER


# ── HTTP endpoint tests ───────────────────────────────────────────────────────

def test_transcribe_requires_auth():
    """No token → 401"""
    client = _make_client(with_auth=False)
    resp = client.post(
        "/api/transcribe",
        files={"file": ("test.webm", b"fake audio", "audio/webm")},
    )
    assert resp.status_code == 401


def test_transcribe_gate_off_returns_503():
    """VOICE_ENABLED=false → 503"""
    client = _make_client(with_auth=True)
    with patch("config.VOICE_ENABLED", False):
        resp = client.post(
            "/api/transcribe",
            files={"file": ("test.webm", b"fake audio", "audio/webm")},
            headers={"Authorization": "Bearer fake-token"},
        )
    assert resp.status_code == 503


def test_transcribe_stub_returns_200():
    """VOICE_ENABLED=true + stub → 200 + placeholder + stub:true"""
    client = _make_client(with_auth=True)
    resp = client.post(
        "/api/transcribe",
        files={"file": ("test.webm", b"fake audio", "audio/webm")},
        headers={"Authorization": "Bearer fake-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == STUB_PLACEHOLDER
    assert data["backend"] == "stub"
    assert data["stub"] is True
