"""Closing-intent cascade — tier-2 semantic scorer + shared request veto. No live NIM/DB.

Covers: closing_score cosine math + fail-safes (mocked embed), the _looks_like_request veto
table, and the tier-2 band constants. Tier-1 lexicon lives in test_reasoning_loop.py::TestAckDetector.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest

import llm.closing_intent as ci
from llm.closing_intent import closing_score, CLOSING_THRESHOLD, _TIER2_MIN_TOKENS, _TIER2_MAX_TOKENS
from llm.router import _looks_like_request


# ── closing_score cosine math + fail-safes ───────────────────────────────────

@pytest.mark.asyncio
async def test_score_none_and_empty_are_zero():
    assert await closing_score(None) == 0.0
    assert await closing_score([]) == 0.0


@pytest.mark.asyncio
async def test_score_no_anchors_is_zero(monkeypatch):
    async def _no_anchors():
        return None
    monkeypatch.setattr(ci, "get_anchors", _no_anchors)
    assert await closing_score([0.1] * 8) == 0.0


@pytest.mark.asyncio
async def test_score_is_max_cosine_over_anchors(monkeypatch):
    # Two orthogonal unit anchors; a query aligned with the second must score ~1.0 (nearest-example
    # MAX, not the mean — a mean of the two would score ~0.71).
    a1 = ci._normalize([1.0, 0.0, 0.0])
    a2 = ci._normalize([0.0, 1.0, 0.0])
    async def _anchors():
        return [a1, a2]
    monkeypatch.setattr(ci, "get_anchors", _anchors)
    assert await closing_score([0.0, 5.0, 0.0]) == pytest.approx(1.0, abs=1e-6)
    assert await closing_score([0.0, 0.0, 3.0]) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.asyncio
async def test_build_anchors_partial_returns_none(monkeypatch):
    # If the embedder drops any phrase, the anchor set is incomplete → refuse (None), so the
    # tuned threshold is never applied to a mistuned cloud.
    calls = {"n": 0}
    async def _flaky(text, *, retries=6):
        calls["n"] += 1
        return None if calls["n"] % 3 == 0 else [0.1, 0.2, 0.3]
    monkeypatch.setattr(ci, "_embed_phrase", _flaky)
    assert await ci._build_anchors() is None


# ── shared request veto ──────────────────────────────────────────────────────

class TestRequestVeto:
    # A veto=True message can NEVER be reclassified closing (precision backstop).
    VETOED = [
        "thanks, but the formula is wrong",     # contrast marker
        "appreciate it, though i have another question",  # 'another'
        "actually that's not right",            # 'actually'
        "wait, what does this do",              # 'wait' + '?'-free but marker
        "ok how about arrays?",                 # '?'
        "thanks for the 3 examples",            # digit
        "check https://example.com for me",     # url
        "run it and show me the output",        # task verb 'run'
        "delete that column please",            # task verb 'delete'
        "update the total row",                 # task verb 'update'
    ]
    NOT_VETOED = [
        "thanks that's all",
        "appreciate the help, i'm all set now",  # 'now' is NOT a veto marker
        "no more questions, thank you",          # 'more' is NOT a veto marker
        "that's everything for now, thank you",
        "cool, thanks a lot",
    ]

    def test_vetoed(self):
        for m in self.VETOED:
            assert _looks_like_request(m) is True, m

    def test_not_vetoed(self):
        for m in self.NOT_VETOED:
            assert _looks_like_request(m) is False, m


# ── band constants sanity ────────────────────────────────────────────────────

def test_band_and_threshold_sane():
    assert 0 < _TIER2_MIN_TOKENS <= _TIER2_MAX_TOKENS
    assert 0.0 < CLOSING_THRESHOLD < 1.0
    # tier-2 owns the medium band; ultra-short (≤2) is tier-1 / trivial-skip territory
    assert _TIER2_MIN_TOKENS >= 3
