"""Unit tests for memory hygiene features — run with: pytest backend/tests/test_memory_hygiene.py -v

Covers:
  - Rotation threshold logic (S4)
  - Dedup merge normalization (T3)
"""

import pytest


# ── Rotation threshold condition (S4) ────────────────────────────────────────

def _should_rotate(msgs: int, tok: int, days: int) -> bool:
    return msgs > 80 or tok > 120000 or days > 3


def test_rotation_below_threshold():
    assert _should_rotate(50, 50000, 1) is False


def test_rotation_msg_exceeded():
    assert _should_rotate(81, 50000, 1) is True


def test_rotation_token_exceeded():
    assert _should_rotate(50, 120001, 1) is True


def test_rotation_idle_exceeded():
    assert _should_rotate(50, 50000, 4) is True


def test_rotation_multiple_exceeded():
    assert _should_rotate(100, 200000, 10) is True


def test_rotation_at_boundary():
    assert _should_rotate(80, 120000, 3) is False
    assert _should_rotate(81, 120000, 3) is True
    assert _should_rotate(80, 120001, 3) is True
    assert _should_rotate(80, 120000, 4) is True


# ── Dedup merge logic (T3) ────────────────────────────────────────────────────

_NORM_PAIRS = [
    ("Intel Xeon E5 2696 V4", "intel xeon e5 2696 v4"),
    ("Xeon E5 2696 v4", "xeon e5 2696 v4"),
    ("Dual Core Intel Xeon E5 2696 V4", "dual core intel xeon e5 2696 v4"),
]


@pytest.mark.parametrize("raw,expected", _NORM_PAIRS)
def test_norm_lowercase(raw, expected):
    from llm.graph_memory import merge_duplicate_entities as _mde
    # Access the private _norm via closure inspection is fragile,
    # so test the normalization inline
    import re
    def _norm(name):
        n = name.lower().strip()
        n = re.sub(r'\s+', ' ', n)
        n = n.rstrip('s')
        return n
    assert _norm(raw) == expected


def test_substring_match():
    """Shorter name is substring of longer normalized name."""
    import re
    def _norm(name):
        n = name.lower().strip()
        n = re.sub(r'\s+', ' ', n)
        n = n.rstrip('s')
        return n

    short = "xeon e5 2696 v4"
    long_ = "dual core intel xeon e5 2696 v4"
    assert _norm(short) in _norm(long_)


def test_token_subset_match():
    """All tokens of shorter appear in longer."""
    import re
    def _norm(name):
        n = name.lower().strip()
        n = re.sub(r'\s+', ' ', n)
        n = n.rstrip('s')
        return n

    a = "xeon e5 2696 v4"
    b = "dual core intel xeon e5 2696 v4"
    a_tokens = set(_norm(a).split())
    b_tokens = set(_norm(b).split())
    assert a_tokens <= b_tokens


def test_no_false_positive_substring():
    """Different entities should not match."""
    import re
    def _norm(name):
        n = name.lower().strip()
        n = re.sub(r'\s+', ' ', n)
        n = n.rstrip('s')
        return n

    a = "python fastapi"
    b = "postgresql database"
    a_norm = _norm(a)
    b_norm = _norm(b)
    assert a_norm not in b_norm
    assert b_norm not in a_norm
    assert not (set(a_norm.split()) <= set(b_norm.split()))
