"""Retrieval eval harness — tests fusion modes against fixed dataset."""
import pytest
from tests.retrieval.conftest import (
    CONV_ID, QUERY_EMB_1024, FILE_ID_A, CHUNK_A_ID,
    TEST_CASES, FILE_TEST_CASES, _mock_db,
    _make_vector_row,
    recall_at_k, mrr, citation_coverage,
)
from llm.retriever import retrieve, retrieve_from_files


# ── retrieve tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("tc", TEST_CASES, ids=[t["name"] for t in TEST_CASES])
@pytest.mark.parametrize("fusion_mode,alpha", [
    ("rrf", None),
    ("weighted", 0.3),
    ("weighted", 0.5),
    ("weighted", 0.7),
], ids=["rrf_k60", "weighted_a0.3", "weighted_a0.5", "weighted_a0.7"])
async def test_retrieve_fusion_modes(tc, fusion_mode, alpha):
    kwargs = dict(
        fusion_mode=fusion_mode,
        k_dense=20,
        k_sparse=20,
    )
    if fusion_mode == "weighted":
        kwargs["alpha"] = alpha

    db = _mock_db(tc["vector_rows"], tc["bm25_rows"])
    results, debug = await retrieve(
        db, tc["query_emb"], CONV_ID,
        top_k=5, query_text=tc["query_text"],
        debug=True, **kwargs,
    )

    chunk_ids = {r["chunk_id"] for r in results}
    expected_id = tc["expected_top1"]

    if expected_id is not None:
        assert expected_id in chunk_ids, \
            f"[{tc['name']}/{fusion_mode}] expected {expected_id} in results, got {chunk_ids}"

    r = recall_at_k(results, tc["expected_chunk_ids"], 3)
    assert r >= 0.5, \
        f"[{tc['name']}/{fusion_mode}] recall@3 {r:.3f} < 0.5"

    mr = mrr(results, tc["expected_chunk_ids"])
    assert mr >= 0.25, \
        f"[{tc['name']}/{fusion_mode}] MRR {mr:.3f} < 0.25"

    cc = citation_coverage(results, tc["expected_sources"])
    assert cc >= 0.8, \
        f"[{tc['name']}/{fusion_mode}] coverage {cc:.3f} < 0.8"

    assert len(debug) == len(results)
    for d in debug:
        assert "chunk_id" in d
        assert "source_id" in d
        assert "score" in d
        assert "rank" in d
        assert "fusion_mode" in d
        assert d["fusion_mode"] == fusion_mode


# ── retrieve_from_files tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("tc", FILE_TEST_CASES, ids=[t["name"] for t in FILE_TEST_CASES])
@pytest.mark.parametrize("fusion_mode,alpha", [
    ("rrf", None),
    ("weighted", 0.5),
], ids=["rrf_k60", "weighted_a0.5"])
async def test_retrieve_from_files_fusion_modes(tc, fusion_mode, alpha):
    kwargs = dict(
        fusion_mode=fusion_mode,
        k_dense=20,
        k_sparse=20,
    )
    if fusion_mode == "weighted":
        kwargs["alpha"] = alpha

    db = _mock_db(tc["vector_rows"], tc["bm25_rows"])
    results, debug = await retrieve_from_files(
        db, tc["query_emb"], tc["file_ids"],
        top_k=5, query_text=tc["query_text"],
        debug=True, **kwargs,
    )

    expected_id = tc["expected_top1"]
    if expected_id is None:
        assert results == []
        assert debug == []
        return

    chunk_ids = {r["chunk_id"] for r in results}
    assert expected_id in chunk_ids, \
        f"[{tc['name']}/{fusion_mode}] expected {expected_id} in results, got {chunk_ids}"

    r = recall_at_k(results, tc["expected_chunk_ids"], 3)
    assert r >= 0.5, \
        f"[{tc['name']}/{fusion_mode}] recall@3 {r:.3f} < 0.5"

    cc = citation_coverage(results, tc["expected_sources"])
    assert cc >= 0.8, \
        f"[{tc['name']}/{fusion_mode}] coverage {cc:.3f} < 0.8"

    assert len(debug) == len(results)
    for d in debug:
        assert d["fusion_mode"] == fusion_mode


# ── cross-mode consistency ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_debug_flag_off_returns_normal():
    """When debug=False (default), retrieve returns just a list, not tuple."""
    db = _mock_db(
        [_make_vector_row(CHUNK_A_ID, CONV_ID, "content", 0.9)],
        [],
    )
    result = await retrieve(db, QUERY_EMB_1024, CONV_ID, top_k=3, query_text="test")
    assert isinstance(result, list)
    assert not isinstance(result, tuple)


@pytest.mark.asyncio
async def test_retrieve_from_files_debug_flag_off_returns_normal():
    """When debug=False (default), retrieve_from_files returns just a list."""
    db = _mock_db(
        [_make_vector_row(CHUNK_A_ID, FILE_ID_A, "content", 0.9)],
        [],
    )
    result = await retrieve_from_files(
        db, QUERY_EMB_1024, [FILE_ID_A], top_k=3, query_text="test"
    )
    assert isinstance(result, list)
    assert not isinstance(result, tuple)
