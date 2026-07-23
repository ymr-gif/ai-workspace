"""Stream wall-clock + token bounds (BUGS.md "No total-stream-duration cap").

Unit tier — no live NIM, no DB, no Redis. Covers the three new bounds:
  - STREAM_TOTAL_TIMEOUT  — one call_stream connection (llm/nim.py)
  - STREAM_TURN_BUDGET    — the whole user turn, across every tool iteration
                             and every fallback-chain model (llm/service/stream.py)
  - STREAM_MAX_TURN_TOKENS — accumulated output tokens across the whole turn

And the abort contract: on exceed, stop yielding and end the generator cleanly
(no raise, no record_failure — the model is slow, not failed), naming the bound
that fired in the reason string. api/chat/stream.py:453-462 turns that `error`
event into status="partial" whenever tokens already streamed (untouched here;
covered indirectly by asserting tokens precede the error event).
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest

import config
import llm.client as llm_client
from llm import nim
from llm.circuit_breaker import _failures, _open, _open_time
from llm.service import stream as svc_stream


# ── shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_circuit_state():
    _failures.clear()
    _open.clear()
    _open_time.clear()
    yield
    _failures.clear()
    _open.clear()
    _open_time.clear()


def _make_clock(start: float = 0.0, step: float = 50.0):
    """A fake time.monotonic() that advances by `step` on every call, starting
    at `start` on the first call. Lets a test control elapsed wall-clock time
    deterministically instead of sleeping in real time."""
    state = {"n": -1}

    def _clock():
        state["n"] += 1
        return start + state["n"] * step

    return _clock


# ── llm.nim.call_stream — per-connection cap (STREAM_TOTAL_TIMEOUT) ─────────

class _FakeStreamCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class _FakeSSEResponse:
    """status_code=200 + aiter_lines() replaying SSE 'data: ...' lines, each
    optionally delayed so a test can force the wall-clock check to trip."""
    def __init__(self, chunks):
        self.status_code = 200
        self._chunks = chunks  # list of (delay_seconds, content_str | None)

    async def aiter_lines(self):
        for delay, content in self._chunks:
            if delay:
                await asyncio.sleep(delay)
            if content is None:
                yield "data: [DONE]"
            else:
                payload = {"choices": [{"delta": {"content": content}, "finish_reason": None}]}
                yield f"data: {json.dumps(payload)}"


class _FakeHTTPClient:
    def __init__(self, response):
        self._response = response

    def stream(self, method, url, headers=None, json=None, timeout=None):
        return _FakeStreamCM(self._response)


class TestConnectionBudget:
    """STREAM_TOTAL_TIMEOUT, enforced inside llm.nim.call_stream."""

    @pytest.mark.asyncio
    async def test_fires_on_trickling_stream_no_record_failure(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TOTAL_TIMEOUT", 0.05)
        monkeypatch.setattr(config, "MAX_RETRIES", 0)

        fake_response = _FakeSSEResponse([
            (0,    "hello "),
            (0.15, "world"),   # arrives well after the 50ms budget elapses
            (0,    None),
        ])
        monkeypatch.setattr(llm_client, "client", _FakeHTTPClient(fake_response))

        failed_models = []

        async def _spy_record_failure(model):
            failed_models.append(model)

        monkeypatch.setattr(nim, "record_failure", _spy_record_failure)

        chunks = []
        async for chunk in nim.call_stream("test-model", [{"role": "user", "content": "hi"}], "rid-1"):
            chunks.append(chunk)

        assert chunks[0] == "hello "
        assert any(isinstance(c, dict) and c.get("__budget_exceeded__") for c in chunks)
        assert "world" not in chunks  # cut before the trickling second chunk arrived
        assert failed_models == []   # never trips the breaker — the model is slow, not failed

    @pytest.mark.asyncio
    async def test_disabled_streams_to_completion(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TOTAL_TIMEOUT", 0)
        monkeypatch.setattr(config, "MAX_RETRIES", 0)

        fake_response = _FakeSSEResponse([
            (0,    "hello "),
            (0.02, "world"),
            (0,    None),
        ])
        monkeypatch.setattr(llm_client, "client", _FakeHTTPClient(fake_response))

        chunks = []
        async for chunk in nim.call_stream("test-model", [{"role": "user", "content": "hi"}], "rid-2"):
            chunks.append(chunk)

        assert chunks == ["hello ", "world"]
        assert not any(isinstance(c, dict) and c.get("__budget_exceeded__") for c in chunks)


# ── _check_turn_budget helper — direct unit coverage of the disable/fire logic ──

class TestCheckTurnBudgetHelper:
    def test_turn_time_bound_fires(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TURN_BUDGET", 10)
        monkeypatch.setattr(config, "STREAM_MAX_TURN_TOKENS", 0)
        reason = svc_stream._check_turn_budget(turn_start=0.0, token_chars=0)
        assert reason is not None
        assert "turn time budget exceeded (10s)" in reason

    def test_turn_time_bound_disabled_ignores_huge_elapsed(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TURN_BUDGET", 0)
        monkeypatch.setattr(config, "STREAM_MAX_TURN_TOKENS", 0)
        assert svc_stream._check_turn_budget(turn_start=0.0, token_chars=0) is None

    def test_token_bound_fires(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TURN_BUDGET", 0)
        monkeypatch.setattr(config, "STREAM_MAX_TURN_TOKENS", 5)
        reason = svc_stream._check_turn_budget(turn_start=0.0, token_chars=100)  # ~25 est tok
        assert reason is not None
        assert "output token budget exceeded (5 tok)" in reason

    def test_token_bound_disabled_ignores_huge_count(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TURN_BUDGET", 0)
        monkeypatch.setattr(config, "STREAM_MAX_TURN_TOKENS", 0)
        assert svc_stream._check_turn_budget(turn_start=0.0, token_chars=10_000_000) is None

    def test_both_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TURN_BUDGET", 0)
        monkeypatch.setattr(config, "STREAM_MAX_TURN_TOKENS", 0)
        assert svc_stream._check_turn_budget(turn_start=0.0, token_chars=10_000_000) is None


# ── generate_stream end-to-end — turn budget + token ceiling + abort shape ───

async def _consume(model_params=None, **kw):
    events = []
    async for ev in svc_stream.generate_stream(
        message="hi", history=[], memory_sheet="", project_summary="",
        history_summary="", retrieved_chunks=[], request_id="rid-svc",
        model_override="test-model", model_params=model_params, db=None,
        **kw,
    ):
        events.append(ev)
    return events


class TestTurnBudgetAcrossIterations:
    @pytest.mark.asyncio
    async def test_fires_across_tool_iterations_not_on_first(self, monkeypatch):
        # Disable the per-connection + token bounds so only the turn-time bound
        # can possibly fire — isolates which bound trips.
        monkeypatch.setattr(config, "STREAM_TOTAL_TIMEOUT", 0)
        monkeypatch.setattr(config, "STREAM_MAX_TURN_TOKENS", 0)
        monkeypatch.setattr(config, "STREAM_TURN_BUDGET", 120)

        # Deterministic fake clock: turn_start reads 0.0; every subsequent
        # time.monotonic() call advances by 50s. Two full tool iterations
        # (each reads the clock 3x: the per-iteration budget check, _t_call,
        # and the post-call _call_ms) land the turn-budget check for
        # iteration #2 at elapsed=200s > 120s — it must NOT fire on iteration #1
        # (elapsed=50s there).
        monkeypatch.setattr(svc_stream.time, "monotonic", _make_clock(start=0.0, step=50.0))

        call_count = {"n": 0}

        async def _fake_call_stream(model, messages, request_id, model_params, tools):
            call_count["n"] += 1
            yield {"__tool_calls__": [{
                "id": "call-1", "type": "function",
                "function": {"name": "web_search", "arguments": json.dumps({"query": f"iter{call_count['n']}"})},
            }]}

        async def _fake_execute_tool(fn_name, args, db, user_id, conv_id):
            return "stub tool result"

        monkeypatch.setattr(svc_stream, "call_stream", _fake_call_stream)
        monkeypatch.setattr(svc_stream, "execute_tool", _fake_execute_tool)

        events = await _consume()

        assert call_count["n"] == 1  # aborted before a second model call was made
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "turn time budget exceeded (120s)" in error_events[0]["message"]
        # the budget event names the bound in the activity trace too
        budget_status = [e for e in events if e["type"] == "status" and e.get("stage") == "budget"
                          and "turn time budget" in e.get("detail", "")]
        assert budget_status
        assert events[-1]["type"] == "error"  # nothing yielded after the abort


class TestTokenCeiling:
    @pytest.mark.asyncio
    async def test_fires_on_accumulated_output_after_tokens_streamed(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TOTAL_TIMEOUT", 0)
        monkeypatch.setattr(config, "STREAM_TURN_BUDGET", 0)
        monkeypatch.setattr(config, "STREAM_MAX_TURN_TOKENS", 10)  # ~40 chars

        async def _fake_call_stream(model, messages, request_id, model_params, tools):
            yield "a" * 100   # ~25 est tokens — already over the 10-tok ceiling
            yield "b" * 100   # must never be reached

        monkeypatch.setattr(svc_stream, "call_stream", _fake_call_stream)

        events = await _consume()

        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 1
        assert token_events[0]["content"] == "a" * 100
        assert not any(e["type"] == "token" and e["content"] == "b" * 100 for e in events)

        # Abort semantics: an error follows tokens already streamed → the partial
        # path in api/chat/stream.py (status="partial" iff accumulated is non-empty).
        assert events[-1]["type"] == "error"
        assert "output token budget exceeded (10 tok)" in events[-1]["message"]
        assert events.index(token_events[0]) < events.index(events[-1])


class TestAllBoundsDisabled:
    @pytest.mark.asyncio
    async def test_normal_turn_completes_with_no_budget_events(self, monkeypatch):
        monkeypatch.setattr(config, "STREAM_TOTAL_TIMEOUT", 0)
        monkeypatch.setattr(config, "STREAM_TURN_BUDGET", 0)
        monkeypatch.setattr(config, "STREAM_MAX_TURN_TOKENS", 0)

        async def _fake_call_stream(model, messages, request_id, model_params, tools):
            yield "hello there"

        monkeypatch.setattr(svc_stream, "call_stream", _fake_call_stream)

        events = await _consume()

        # The context-window-fit status event legitimately reuses stage="budget" at
        # level="info" (llm/service/stream.py:487) — only an error-level "budget"
        # status means one of the three new bounds fired.
        assert not any(e["type"] == "status" and e.get("stage") == "budget" and e.get("level") == "error"
                       for e in events)
        assert any(e["type"] == "done" for e in events)
        assert not any(e["type"] == "error" for e in events)
