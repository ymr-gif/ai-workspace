"""Per-connector intent latch signal tests (Q3 Task B + generalization) — pure unit.

Covers the cosine score math, the None/empty fail-safe (→ 0.0, fail toward NOT
latching), the no-centroid fail-safe, that the centroid is built from
`embed(..., input_type="query")` (must match request-time query encoding for the
asymmetric e5 embedder), and that every connector has phrases + a threshold.
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

import llm.tools.connector_intent as ci

CONNECTORS = ["drive", "calendar", "gmail"]


@pytest.fixture(autouse=True)
def _reset_centroids():
    ci._centroids.clear()
    yield
    ci._centroids.clear()


def test_every_connector_has_phrases_and_threshold():
    for c in CONNECTORS:
        assert ci.INTENT_PHRASES.get(c), f"{c} missing phrases"
        assert len(ci.INTENT_PHRASES[c]) >= 12
        assert isinstance(ci.INTENT_THRESHOLDS.get(c), float)


def test_normalize_is_unit_length():
    v = ci._normalize([3.0, 4.0])
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)


def test_normalize_zero_vector_safe():
    assert ci._normalize([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


@pytest.mark.parametrize("connector", CONNECTORS)
async def test_score_none_query_is_zero(connector):
    ci._centroids[connector] = ci._normalize([1.0, 0.0, 0.0])
    assert await ci.intent_score(connector, None) == 0.0
    assert await ci.intent_score(connector, []) == 0.0


async def test_score_no_centroid_is_zero(monkeypatch):
    async def _no_centroid(connector):
        return None
    monkeypatch.setattr(ci, "get_centroid", _no_centroid)
    assert await ci.intent_score("drive", [0.1, 0.2, 0.3]) == 0.0


async def test_score_cosine_aligned_and_orthogonal():
    ci._centroids["calendar"] = ci._normalize([1.0, 0.0, 0.0])
    assert math.isclose(await ci.intent_score("calendar", [5.0, 0.0, 0.0]), 1.0, rel_tol=1e-9)
    assert math.isclose(await ci.intent_score("calendar", [0.0, 7.0, 0.0]), 0.0, abs_tol=1e-9)
    assert math.isclose(await ci.intent_score("calendar", [-2.0, 0.0, 0.0]), -1.0, rel_tol=1e-9)


async def test_centroid_built_as_query_encoded_mean(monkeypatch):
    seen_input_types = []

    async def _fake_embed(text, input_type="passage"):
        seen_input_types.append(input_type)
        return [1.0, 0.0]  # all phrases map to one point → centroid == that point

    monkeypatch.setattr(ci, "embed_text", _fake_embed)
    centroid = await ci.get_centroid("gmail")
    assert centroid is not None
    assert math.isclose(centroid[0], 1.0, rel_tol=1e-9)
    assert math.isclose(centroid[1], 0.0, abs_tol=1e-9)
    # Every phrase embedded as a QUERY (asymmetric e5 — matches request time).
    assert seen_input_types and all(t == "query" for t in seen_input_types)


async def test_centroid_none_when_embeds_incomplete(monkeypatch):
    # A phrase that exhausts its retries → partial set → refuse to build (mistuned
    # centroid is worse than none; lazy path retries later).
    async def _fail_phrase(text, retries=6):
        return None
    monkeypatch.setattr(ci, "_embed_phrase", _fail_phrase)
    assert await ci.get_centroid("drive") is None
