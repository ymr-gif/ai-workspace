"""Unit tests for health-gated chat-endpoint failover — no NIM, no Redis.

Run: pytest backend/tests/test_endpoint_failover.py -v

Covers:
  - disabled by default → returns NIM_URL, never probes (byte-identical to today)
  - enabled + primary healthy → returns primary
  - enabled + primary down → returns NIM
  - health verdict is cached (no re-probe within TTL)
  - mark_primary_unhealthy() forces NIM without a probe
  - is_primary() only matches the configured primary (a NIM failure never demotes)
  - _probe_url() derives /models correctly
  - CHAT ONLY: there is no embedding failover symbol (guards the vector-space rule)
"""
import time

import pytest

import config
import llm.endpoint as ep


NIM = "https://integrate.api.nvidia.com/v1/chat/completions"
PRIMARY = "http://10.8.0.2:8080/v1/chat/completions"


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # Deterministic config + no Redis so the in-process cache path is exercised.
    monkeypatch.setattr(config, "NIM_URL", NIM, raising=False)
    monkeypatch.setattr(config, "USE_REDIS", False, raising=False)
    monkeypatch.setattr(config, "LLM_HEALTH_TTL", 15, raising=False)
    monkeypatch.setattr(config, "LLM_HEALTH_TIMEOUT", 2.0, raising=False)
    ep._local.clear()
    yield
    ep._local.clear()


def _set(monkeypatch, *, enabled, primary=PRIMARY):
    monkeypatch.setattr(config, "LLM_FAILOVER_ENABLED", enabled, raising=False)
    monkeypatch.setattr(config, "LLM_PRIMARY_URL", primary, raising=False)


def _stub_probe(monkeypatch, result, counter=None):
    async def fake(url):
        if counter is not None:
            counter.append(url)
        return result
    monkeypatch.setattr(ep, "_probe", fake)


# ── disabled path ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_disabled_returns_nim_no_probe(monkeypatch):
    _set(monkeypatch, enabled=False)
    calls = []
    _stub_probe(monkeypatch, True, calls)
    assert await ep.pick_chat_url() == NIM
    assert calls == []  # never probed


@pytest.mark.asyncio
async def test_enabled_but_no_primary_returns_nim(monkeypatch):
    _set(monkeypatch, enabled=True, primary="")
    calls = []
    _stub_probe(monkeypatch, True, calls)
    assert await ep.pick_chat_url() == NIM
    assert calls == []


# ── enabled path ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_primary_healthy_returns_primary(monkeypatch):
    _set(monkeypatch, enabled=True)
    _stub_probe(monkeypatch, True)
    assert await ep.pick_chat_url() == PRIMARY


@pytest.mark.asyncio
async def test_primary_down_returns_nim(monkeypatch):
    _set(monkeypatch, enabled=True)
    _stub_probe(monkeypatch, False)
    assert await ep.pick_chat_url() == NIM


@pytest.mark.asyncio
async def test_health_verdict_cached_no_reprobe(monkeypatch):
    _set(monkeypatch, enabled=True)
    calls = []
    _stub_probe(monkeypatch, True, calls)
    assert await ep.pick_chat_url() == PRIMARY
    assert await ep.pick_chat_url() == PRIMARY
    assert await ep.pick_chat_url() == PRIMARY
    assert len(calls) == 1  # probed once, then served from cache


@pytest.mark.asyncio
async def test_cache_expiry_triggers_reprobe(monkeypatch):
    _set(monkeypatch, enabled=True)
    calls = []
    _stub_probe(monkeypatch, True, calls)
    assert await ep.pick_chat_url() == PRIMARY
    # expire the in-process cache
    ep._local["until"] = time.monotonic() - 1
    assert await ep.pick_chat_url() == PRIMARY
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_mark_unhealthy_forces_nim_without_probe(monkeypatch):
    _set(monkeypatch, enabled=True)
    calls = []
    _stub_probe(monkeypatch, True, calls)  # would say healthy if asked
    await ep.mark_primary_unhealthy()
    assert await ep.pick_chat_url() == NIM
    assert calls == []  # cached-unhealthy short-circuits the probe


@pytest.mark.asyncio
async def test_mark_unhealthy_noop_when_disabled(monkeypatch):
    _set(monkeypatch, enabled=False)
    await ep.mark_primary_unhealthy()
    assert ep._local == {}  # nothing cached


# ── is_primary + probe-url helpers ────────────────────────────────────────────

def test_is_primary_matches_only_primary(monkeypatch):
    _set(monkeypatch, enabled=True)
    assert ep.is_primary(PRIMARY) is True
    assert ep.is_primary(NIM) is False  # a NIM failure must never demote the primary


def test_is_primary_false_when_no_primary(monkeypatch):
    _set(monkeypatch, enabled=True, primary="")
    assert ep.is_primary("") is False


@pytest.mark.parametrize("chat_url,expected", [
    ("http://10.8.0.2:8080/v1/chat/completions", "http://10.8.0.2:8080/v1/models"),
    ("https://integrate.api.nvidia.com/v1/chat/completions", "https://integrate.api.nvidia.com/v1/models"),
    ("http://host:8080/v1/", "http://host:8080/v1/models"),
    ("http://host:8080/custom", "http://host:8080/custom/models"),
])
def test_probe_url_derivation(chat_url, expected):
    assert ep._probe_url(chat_url) == expected


# ── invariant guard: chat-only, no embedding failover ─────────────────────────

def test_no_embedding_failover_symbol():
    # Enforces the design rule: never fail an embed over to a different embedder
    # (mixes vector spaces). If someone adds one, this test forces a decision.
    assert not hasattr(ep, "pick_embed_url")
