"""Shared fixtures and test data for retrieval eval harness."""
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("NVIDIA_API_KEY",  "test-key")
os.environ.setdefault("DATABASE_URL",    "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret")

# ── fixed dataset ──────────────────────────────────────────────────────────────

CONV_ID   = uuid.uuid4()
FILE_ID_A = uuid.uuid4()
FILE_ID_B = uuid.uuid4()
FILE_ID_C = uuid.uuid4()

CHUNK_A_ID = uuid.uuid4()
CHUNK_B_ID = uuid.uuid4()
CHUNK_C_ID = uuid.uuid4()
CHUNK_D_ID = uuid.uuid4()
CHUNK_E_ID = uuid.uuid4()

QUERY_EMB_1024 = [0.01 * (i % 10) for i in range(1024)]


class MockRows:
    """Fake db.execute() return that exposes .all()."""
    def __init__(self, rows: list[tuple]):
        self._rows = rows
    def all(self):
        return self._rows


def _make_vector_row(chunk_id, source_id, content, sim):
    row = MagicMock()
    row.id = chunk_id
    row.conversation_id = source_id
    row.file_id = source_id
    row.content_snippet = content
    row.content = content
    row.sim = sim
    return row


def _make_bm25_row(chunk_id, source_id, content, rank):
    row = MagicMock()
    row.id = chunk_id
    row.conversation_id = source_id
    row.file_id = source_id
    row.content_snippet = content
    row.content = content
    row.rank = rank
    return row


# Each test case: (name, query_emb, query_text, vector_rows, bm25_rows,
#                   expected_chunk_ids_top1, expected_source_ids_top3)
TEST_CASES = [
    {
        "name": "exact_match",
        "query_emb": QUERY_EMB_1024,
        "query_text": "authentication flow",
        "vector_rows": [
            _make_vector_row(CHUNK_A_ID, CONV_ID, "user authentication via JWT tokens", 0.92),
            _make_vector_row(CHUNK_B_ID, CONV_ID, "password hashing with bcrypt", 0.85),
            _make_vector_row(CHUNK_C_ID, CONV_ID, "session management overview", 0.70),
        ],
        "bm25_rows": [
            _make_bm25_row(CHUNK_A_ID, CONV_ID, "user authentication via JWT tokens", 0.85),
            _make_bm25_row(CHUNK_B_ID, CONV_ID, "password hashing with bcrypt", 0.65),
        ],
        "expected_chunk_ids": {CHUNK_A_ID, CHUNK_B_ID},
        "expected_top1": CHUNK_A_ID,
        "expected_sources": {CONV_ID},
    },
    {
        "name": "fuzzy_bm25_boost",
        "query_emb": QUERY_EMB_1024,
        "query_text": "how do I reset my password",
        "vector_rows": [
            _make_vector_row(CHUNK_A_ID, CONV_ID, "general security guidelines", 0.60),
            _make_vector_row(CHUNK_D_ID, CONV_ID, "API rate limiting", 0.55),
        ],
        "bm25_rows": [
            _make_bm25_row(CHUNK_B_ID, CONV_ID, "password reset instructions step by step", 0.92),
            _make_bm25_row(CHUNK_C_ID, CONV_ID, "forgot password email flow", 0.78),
        ],
        "expected_chunk_ids": {CHUNK_B_ID, CHUNK_C_ID},
        "expected_top1": CHUNK_B_ID,
        "expected_sources": {CONV_ID},
    },
    {
        "name": "multi_source",
        "query_emb": QUERY_EMB_1024,
        "query_text": "file processing pipeline",
        "vector_rows": [
            _make_vector_row(CHUNK_A_ID, FILE_ID_A, "PDF extraction and parsing", 0.88),
            _make_vector_row(CHUNK_B_ID, FILE_ID_B, "DOCX table extraction", 0.82),
            _make_vector_row(CHUNK_C_ID, FILE_ID_C, "XLSX cell parsing logic", 0.75),
        ],
        "bm25_rows": [
            _make_bm25_row(CHUNK_B_ID, FILE_ID_B, "DOCX table extraction", 0.90),
            _make_bm25_row(CHUNK_A_ID, FILE_ID_A, "PDF extraction and parsing", 0.70),
        ],
        "expected_chunk_ids": {CHUNK_A_ID, CHUNK_B_ID, CHUNK_C_ID},
        "expected_top1": CHUNK_A_ID,
        "expected_sources": {FILE_ID_A, FILE_ID_B},
    },
    {
        "name": "vector_only_fallback",
        "query_emb": QUERY_EMB_1024,
        "query_text": "",
        "vector_rows": [
            _make_vector_row(CHUNK_D_ID, CONV_ID, "vector only result alpha", 0.95),
            _make_vector_row(CHUNK_E_ID, CONV_ID, "vector only result beta", 0.89),
            _make_vector_row(CHUNK_A_ID, CONV_ID, "vector only result gamma", 0.72),
        ],
        "bm25_rows": [],
        "expected_chunk_ids": {CHUNK_D_ID, CHUNK_E_ID},
        "expected_top1": CHUNK_D_ID,
        "expected_sources": {CONV_ID},
    },
    {
        "name": "single_source",
        "query_emb": QUERY_EMB_1024,
        "query_text": "docker compose setup",
        "vector_rows": [
            _make_vector_row(CHUNK_A_ID, CONV_ID, "docker compose file structure", 0.91),
            _make_vector_row(CHUNK_B_ID, CONV_ID, "container networking config", 0.80),
        ],
        "bm25_rows": [
            _make_bm25_row(CHUNK_A_ID, CONV_ID, "docker compose file structure", 0.88),
        ],
        "expected_chunk_ids": {CHUNK_A_ID},
        "expected_top1": CHUNK_A_ID,
        "expected_sources": {CONV_ID},
    },
]

FILE_TEST_CASES = [
    {
        "name": "file_exact_match",
        "query_emb": QUERY_EMB_1024,
        "query_text": "PDF parsing",
        "file_ids": [FILE_ID_A, FILE_ID_B, FILE_ID_C],
        "vector_rows": [
            _make_vector_row(CHUNK_A_ID, FILE_ID_A, "PDF text extraction algorithm", 0.93),
            _make_vector_row(CHUNK_B_ID, FILE_ID_B, "PDF image extraction", 0.78),
        ],
        "bm25_rows": [
            _make_bm25_row(CHUNK_A_ID, FILE_ID_A, "PDF text extraction algorithm", 0.90),
        ],
        "expected_chunk_ids": {CHUNK_A_ID},
        "expected_top1": CHUNK_A_ID,
        "expected_sources": {FILE_ID_A},
    },
    {
        "name": "file_empty_no_file_ids",
        "query_emb": QUERY_EMB_1024,
        "query_text": "anything",
        "file_ids": [],
        "vector_rows": [],
        "bm25_rows": [],
        "expected_chunk_ids": set(),
        "expected_top1": None,
        "expected_sources": set(),
    },
]


# ── mock helpers ───────────────────────────────────────────────────────────────

def _mock_db(vector_rows, bm25_rows, side_effects=None):
    """Create an AsyncSession mock whose execute() returns controlled rows.

    First call to execute returns vector_rows, second (if bm25_rows non-empty)
    returns bm25_rows. Uses call_count tracking.
    """
    db = AsyncMock(spec=object)
    db.execute = AsyncMock()

    if side_effects:
        db.execute.side_effect = side_effects
    else:
        calls = [MockRows(vector_rows)]
        if bm25_rows:
            calls.append(MockRows(bm25_rows))
        db.execute.side_effect = calls

    return db


# ── metrics helpers ────────────────────────────────────────────────────────────

def recall_at_k(results, expected_ids, k):
    top_k_ids = {r["chunk_id"] for r in results[:k]}
    return len(top_k_ids & expected_ids) / len(expected_ids) if expected_ids else 1.0


def mrr(results, expected_ids):
    for i, r in enumerate(results):
        if r["chunk_id"] in expected_ids:
            return 1.0 / (i + 1)
    return 0.0


def citation_coverage(results, expected_sources):
    if not expected_sources:
        return 1.0
    covered = {r["source_id"] for r in results if r["source_id"] in expected_sources}
    return len(covered) / len(expected_sources)
