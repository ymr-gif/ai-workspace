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
  - Redis unreachable → the read side falls back to the local cache (no probe storm)

Plus the llm/nim.py wiring, which the endpoint unit tests above cannot reach:
  - ANY non-200 from the primary demotes the ENDPOINT and re-picks NIM next attempt
  - ...and never calls record_failure(), i.e. never opens the model breaker
  - a non-200 from NIM keeps its pre-failover breaker behaviour
  - NVIDIA_API_KEY is never sent to the primary
"""
import time

import pytest

import config
import llm.client as llm_client
import llm.endpoint as ep
import llm.nim as nim


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


# ── cache: Redis down must not turn into a probe-per-request ──────────────────

@pytest.mark.asyncio
async def test_redis_error_falls_back_to_local_cache(monkeypatch):
    """_set_cached() falls through to _local when Redis is down, so _get_cached()
    must read it back. Otherwise the write side throttles, the read side never
    sees a verdict, and every single call pays a probe timeout."""
    import core.redis_client as rc

    def boom():
        raise RuntimeError("redis down")
    monkeypatch.setattr(rc, "get_redis", boom)
    monkeypatch.setattr(config, "USE_REDIS", True, raising=False)
    _set(monkeypatch, enabled=True)

    calls = []
    _stub_probe(monkeypatch, True, calls)
    assert await ep.pick_chat_url() == PRIMARY
    assert await ep.pick_chat_url() == PRIMARY
    assert await ep.pick_chat_url() == PRIMARY
    assert len(calls) == 1  # probed once, then served from the local fallback


# ── llm/nim.py wiring ─────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status_code, payload=None, lines=None):
        self.status_code = status_code
        self.text = ""
        self._payload = payload or {}
        self._lines = lines or []

    def json(self):
        return self._payload

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _StreamCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    """Replays a queued response list; the last entry repeats. Records each
    (url, headers) so a test can assert which endpoint an attempt actually hit."""

    def __init__(self, *responses):
        self._queue = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def _next(self, url, headers):
        self.calls.append((url, headers))
        return self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]

    @property
    def urls(self):
        return [url for url, _ in self.calls]

    async def post(self, url, headers=None, json=None):
        return self._next(url, headers)

    def stream(self, method, url, headers=None, json=None, timeout=None):
        return _StreamCtx(self._next(url, headers))


OK_PAYLOAD = {"choices": [{"message": {"content": "hi"}}], "usage": {"total_tokens": 3}}
OK_LINES = ['data: {"choices":[{"delta":{"content":"hi"},"finish_reason":null}]}',
            "data: [DONE]"]


@pytest.fixture
def wired(monkeypatch):
    """nim.py with a fake HTTP client and counted breaker calls."""
    import asyncio

    failures: list[str] = []

    async def fake_record_failure(model):
        failures.append(model)

    monkeypatch.setattr(nim, "is_open", lambda model: False)
    monkeypatch.setattr(nim, "record_failure", fake_record_failure)
    monkeypatch.setattr(nim, "record_success", lambda model: None)
    monkeypatch.setattr(nim, "MAX_RETRIES", 2, raising=False)
    monkeypatch.setattr(llm_client, "semaphore", asyncio.Semaphore(1), raising=False)
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "nvapi-secret", raising=False)
    monkeypatch.setattr(config, "LLM_PRIMARY_API_KEY", "", raising=False)
    monkeypatch.setattr(config, "LLM_BACKEND", "nim", raising=False)
    monkeypatch.setattr(config, "STREAM_TOTAL_TIMEOUT", 0, raising=False)
    return failures


def _install(monkeypatch, *responses) -> _FakeClient:
    client = _FakeClient(*responses)
    monkeypatch.setattr(llm_client, "client", client, raising=False)
    return client


async def _drain(model="reasoning"):
    return [c async for c in nim.call_stream(model, [{"role": "user", "content": "x"}], "rid")]


@pytest.mark.parametrize("status", [400, 401, 404, 500, 503])
@pytest.mark.asyncio
async def test_stream_primary_non200_demotes_endpoint_not_model(monkeypatch, wired, status):
    """Regression: this was gated on `status_code >= 500`, so a 404 from a
    misconfigured LLM_PRIMARY_URL fell through to record_failure() and opened the
    model breaker — blocking the NIM fallback it was supposed to switch to."""
    _set(monkeypatch, enabled=True)
    _stub_probe(monkeypatch, True)
    client = _install(monkeypatch, _Resp(status), _Resp(200, lines=OK_LINES))

    chunks = await _drain()

    assert client.urls == [PRIMARY, NIM]   # re-picked per attempt
    assert "hi" in chunks                  # the retry actually answered
    assert wired == []                     # model breaker untouched


@pytest.mark.parametrize("status", [400, 404, 500])
@pytest.mark.asyncio
async def test_call_primary_non200_fails_over_to_nim(monkeypatch, wired, status):
    """call() had the mirror-image bug: a primary 4xx returned an http_ error
    without demoting the endpoint, so every later call hit the same dead URL."""
    _set(monkeypatch, enabled=True)
    _stub_probe(monkeypatch, True)
    client = _install(monkeypatch, _Resp(status), _Resp(200, payload=OK_PAYLOAD))

    result = await nim.call("reasoning", [{"role": "user", "content": "x"}], "rid")

    assert client.urls == [PRIMARY, NIM]
    assert result["ok"] is True and result["content"] == "hi"
    assert wired == []


@pytest.mark.asyncio
async def test_stream_nim_4xx_still_records_failure(monkeypatch, wired):
    """Guards the other direction: the fix must not stop NIM faults from
    reaching the breaker."""
    _set(monkeypatch, enabled=False)
    _install(monkeypatch, _Resp(404))

    assert await _drain() == []
    assert wired == ["reasoning"]


@pytest.mark.asyncio
async def test_call_nim_4xx_returns_error_without_breaker(monkeypatch, wired):
    """Pre-failover behaviour for call(), unchanged: a NIM 4xx is a caller error,
    not a health signal."""
    _set(monkeypatch, enabled=False)
    _install(monkeypatch, _Resp(404))

    result = await nim.call("reasoning", [{"role": "user", "content": "x"}], "rid")

    assert result["ok"] is False and result["error"] == "http_404"
    assert wired == []


@pytest.mark.asyncio
async def test_primary_demotion_survives_into_later_calls(monkeypatch, wired):
    """mark_primary_unhealthy() is cached, so a second request skips the dead
    primary entirely instead of re-paying the failure."""
    _set(monkeypatch, enabled=True)
    _stub_probe(monkeypatch, True)
    client = _install(monkeypatch, _Resp(404), _Resp(200, lines=OK_LINES))

    await _drain()
    await _drain()

    assert client.urls == [PRIMARY, NIM, NIM]  # primary tried once, then skipped
    assert wired == []


# ── credential scoping ────────────────────────────────────────────────────────

def test_nvidia_key_never_sent_to_primary(monkeypatch):
    _set(monkeypatch, enabled=True)
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "nvapi-secret", raising=False)
    monkeypatch.setattr(config, "LLM_PRIMARY_API_KEY", "", raising=False)

    assert "Authorization" not in nim._auth_headers(PRIMARY)
    assert nim._auth_headers(NIM)["Authorization"] == "Bearer nvapi-secret"


def test_primary_gets_its_own_key_when_set(monkeypatch):
    _set(monkeypatch, enabled=True)
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "nvapi-secret", raising=False)
    monkeypatch.setattr(config, "LLM_PRIMARY_API_KEY", "local-key", raising=False)

    assert nim._auth_headers(PRIMARY)["Authorization"] == "Bearer local-key"
    assert nim._auth_headers(NIM)["Authorization"] == "Bearer nvapi-secret"
