"""Unit tests for memory hygiene features — run with: pytest backend/tests/test_memory_hygiene.py -v

Covers:
  - _prune_canvas_corrections (S1)
  - Rotation threshold logic (S4)
"""

import pytest
from llm.summarizer.compact import _prune_canvas_corrections


# ── _prune_canvas_corrections (S1) ──────────────────────────────────────────

def test_no_canvas_terms_unchanged():
    content = "[USER]\nname = Alice\n[STACK]\npython, fastapi\n[PROJECT]\nfoo\n"
    assert _prune_canvas_corrections(content) == content


def test_empty_content():
    assert _prune_canvas_corrections("") == ""


def test_no_corrections_section():
    content = "[USER]\nname = Alice\ncanvas is mentioned outside corrections\n"
    assert _prune_canvas_corrections(content) == content


def test_removes_canvas_entries():
    content = (
        "[USER]\nname = Alice\n"
        "[CORRECTIONS]\n"
        "canvas: some error\n"
        "session node: another\n"
        "workspace node: broken\n"
        "valid note\n"
        "[STACK]\npython\n"
    )
    result = _prune_canvas_corrections(content)
    assert "canvas: some error" not in result
    assert "session node: another" not in result
    assert "workspace node: broken" not in result
    assert "valid note" in result
    assert "[USER]" in result
    assert "[STACK]" in result


def test_keeps_non_canvas_corrections():
    content = (
        "[USER]\n"
        "[CORRECTIONS]\n"
        "normal correction\n"
        "another valid note\n"
        "[STACK]\npython\n"
    )
    result = _prune_canvas_corrections(content)
    assert "normal correction" in result
    assert "another valid note" in result


def test_all_canvas_lines_removed():
    content = (
        "[USER]\n"
        "[CORRECTIONS]\n"
        "canvas error\n"
        "session node glitch\n"
        "[STACK]\n"
    )
    result = _prune_canvas_corrections(content)
    assert "canvas error" not in result
    assert "session node glitch" not in result
    assert "[STACK]" in result


def test_caps_to_20_entries():
    """Cap applies only when pruning occurs — no-prune returns full content."""
    entries = [f"valid note {i}" for i in range(30)]
    content = "[CORRECTIONS]\n" + "\n".join(entries) + "\n[STACK]"
    result = _prune_canvas_corrections(content, max_entries=20)
    # all valid (no canvas terms), so pruned==0 → returns unchanged
    assert "valid note 0" in result
    assert "valid note 29" in result


def test_caps_to_20_with_mixed_canvas():
    entries = [f"canvas error {i}" for i in range(10)] + [f"real note {i}" for i in range(30)]
    content = "[CORRECTIONS]\n" + "\n".join(entries) + "\n[STACK]"
    result = _prune_canvas_corrections(content, max_entries=20)
    # canvas errors removed (10), survivors (30) capped to 20 most recent
    assert "canvas error 0" not in result
    assert "real note 0" not in result
    assert "real note 9" not in result
    assert "real note 10" in result
    assert "real note 29" in result


def test_section_boundary_preserved_after_empty_corrections():
    """When all corrections are canvas, the [CORRECTIONS] header is removed."""
    content = (
        "[USER]\nfoo\n"
        "[CORRECTIONS]\n"
        "canvas fail\n"
        "[STACK]\npython\n"
    )
    result = _prune_canvas_corrections(content)
    assert "[CORRECTIONS]" not in result
    assert "[STACK]" in result


def test_case_insensitive_canvas_detection():
    content = (
        "[CORRECTIONS]\n"
        "CANVAS: broken\n"
        "Session Node: error\n"
        "[STACK]\n"
    )
    result = _prune_canvas_corrections(content)
    assert "CANVAS: broken" not in result


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
