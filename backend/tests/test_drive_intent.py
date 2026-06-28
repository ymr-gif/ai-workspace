"""Drive-intent latch signal tests (Q3 Task B) — pure unit, no NIM/Redis.

Covers the score math (cosine via normalized dot), the None/empty fail-safe
(→ 0.0, fail toward NOT latching), the no-centroid fail-safe, and that the
centroid is built from `embed(..., input_type="query")` (must match the
request-time query encoding for the asymmetric e5 embedder).
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import llm.tools.drive_intent as di


@pytest.fixture(autouse=True)
def _reset_centroid():
    di._centroid = None
    yield
    di._centroid = None


def test_normalize_is_unit_length():
    v = di._normalize([3.0, 4.0])
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)


def test_normalize_zero_vector_safe():
    # No division-by-zero on an all-zero vector.
    assert di._normalize([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


async def test_score_none_query_is_zero():
    di._centroid = di._normalize([1.0, 0.0, 0.0])
    assert await di.drive_intent_score(None) == 0.0
    assert await di.drive_intent_score([]) == 0.0


async def test_score_no_centroid_is_zero(monkeypatch):
    async def _no_centroid():
        return None
    monkeypatch.setattr(di, "get_centroid", _no_centroid)
    assert await di.drive_intent_score([0.1, 0.2, 0.3]) == 0.0


async def test_score_cosine_aligned_and_orthogonal():
    di._centroid = di._normalize([1.0, 0.0, 0.0])
    # Same direction (any magnitude) → cosine 1.0.
    assert math.isclose(await di.drive_intent_score([5.0, 0.0, 0.0]), 1.0, rel_tol=1e-9)
    # Orthogonal → 0.0.
    assert math.isclose(await di.drive_intent_score([0.0, 7.0, 0.0]), 0.0, abs_tol=1e-9)
    # Opposite → -1.0.
    assert math.isclose(await di.drive_intent_score([-2.0, 0.0, 0.0]), -1.0, rel_tol=1e-9)


async def test_centroid_built_as_query_encoded_mean(monkeypatch):
    seen_input_types = []

    async def _fake_embed(text, input_type="passage"):
        seen_input_types.append(input_type)
        return [1.0, 0.0]  # all phrases map to the same point → centroid == that point

    monkeypatch.setattr(di, "embed_text", _fake_embed)
    centroid = await di.get_centroid()
    assert centroid is not None
    assert math.isclose(centroid[0], 1.0, rel_tol=1e-9)
    assert math.isclose(centroid[1], 0.0, abs_tol=1e-9)
    # Every phrase must be embedded as a QUERY (asymmetric e5 — matches request time).
    assert seen_input_types and all(t == "query" for t in seen_input_types)


async def test_centroid_none_when_embeds_incomplete(monkeypatch):
    # _embed_phrase exhausted its retries for a phrase → partial set → refuse to
    # build (mistuned centroid is worse than none; lazy path retries later).
    async def _fail_phrase(text, retries=6):
        return None
    monkeypatch.setattr(di, "_embed_phrase", _fail_phrase)
    assert await di.get_centroid() is None
