"""C3 — retrieval echo dedup. Within-conversation retrieve() must exclude
message-embeddings whose message_id is already in the raw history window sent
verbatim this turn (structural filter, no similarity cutoff, no K constant).

We assert the SQL actually carries the `message_id NOT IN (...)` predicate on BOTH
the dense and the BM25 legs when exclude_message_ids is supplied, and carries
neither when it is not. Cross-conversation retrieve_global is untouched by design.
"""
import uuid

import pytest

from llm.retriever.main import retrieve
from tests.retrieval.conftest import (
    CONV_ID, QUERY_EMB_1024, _mock_db, _make_vector_row, _make_bm25_row, CHUNK_A_ID,
)


def _compiled(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": False}))


@pytest.mark.asyncio
async def test_exclude_ids_applied_to_dense_and_bm25():
    exclude = [uuid.uuid4(), uuid.uuid4()]
    vector_rows = [_make_vector_row(CHUNK_A_ID, CONV_ID, "prior answer echo", 0.99)]
    bm25_rows = [_make_bm25_row(CHUNK_A_ID, CONV_ID, "prior answer echo", 0.9)]
    db = _mock_db(vector_rows, bm25_rows)

    await retrieve(db, QUERY_EMB_1024, CONV_ID, query_text="anything",
                   exclude_message_ids=exclude)

    stmts = [c.args[0] for c in db.execute.call_args_list]
    assert len(stmts) == 2, "expected a dense leg and a bm25 leg"
    for stmt in stmts:
        sql = _compiled(stmt)
        assert "message_id NOT IN" in sql, sql


@pytest.mark.asyncio
async def test_no_exclusion_when_ids_empty():
    vector_rows = [_make_vector_row(CHUNK_A_ID, CONV_ID, "content", 0.8)]
    bm25_rows = [_make_bm25_row(CHUNK_A_ID, CONV_ID, "content", 0.7)]

    for empty in (None, []):
        db = _mock_db(vector_rows, bm25_rows)
        await retrieve(db, QUERY_EMB_1024, CONV_ID, query_text="anything",
                       exclude_message_ids=empty)
        for c in db.execute.call_args_list:
            assert "message_id NOT IN" not in _compiled(c.args[0])
