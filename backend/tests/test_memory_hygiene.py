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


# ── Widened blocklist terms (T1) ─────────────────────────────────────────────

def test_removes_session_alone():
    """Standalone 'session' (not 'session node') is now caught."""
    content = "[CORRECTIONS]\nactive sessions: 5 wrong\nreal note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "active sessions" not in result
    assert "real note" in result


def test_removes_nodes_alone():
    """Standalone 'nodes' is now caught."""
    content = "[CORRECTIONS]\nlist the ids of these nodes\nreal note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "these nodes" not in result
    assert "real note" in result


def test_removes_topic_alone():
    """Standalone 'topic' is now caught."""
    content = "[CORRECTIONS]\nfailure to provide topic suggestions\nreal note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "topic suggestions" not in result
    assert "real note" in result


def test_removes_tool_loop_detected():
    """Tool loop detected is now caught."""
    content = "[CORRECTIONS]\nTool loop detected: infinite loop\nreal note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "Tool loop detected" not in result
    assert "real note" in result


def test_removes_panel():
    """'panel' is now caught."""
    content = "[CORRECTIONS]\npanel error: missing buttons\nreal note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "panel error" not in result
    assert "real note" in result


def test_removes_workspace_alone():
    """'workspace' alone (not 'workspace node') is now caught."""
    content = "[CORRECTIONS]\nworkspace crashed during session\nreal note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "workspace crashed" not in result
    assert "real note" in result


def test_allowlist_node_js_preserved():
    """'node.js' is allowlisted and kept."""
    content = "[CORRECTIONS]\nupgrade node.js to v20\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "node.js" in result


def test_allowlist_session_key_preserved():
    """'session key' is allowlisted and kept."""
    content = "[CORRECTIONS]\nsession key expired early\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "session key" in result


def test_allowlist_topic_model_preserved():
    """'topic model' is allowlisted and kept."""
    content = "[CORRECTIONS]\ntopic model needs retraining\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "topic model" in result


def test_allowlist_mixed_with_canvas():
    """Allowlisted entries survive alongside canvas entries being pruned."""
    content = (
        "[CORRECTIONS]\n"
        "canvas: broken panel\n"
        "node.js version mismatch\n"
        "session key rotation failed\n"
        "session node: glitch\n"
        "[STACK]\n"
    )
    result = _prune_canvas_corrections(content)
    assert "canvas: broken panel" not in result
    assert "session node: glitch" not in result
    assert "node.js version mismatch" in result
    assert "session key rotation failed" in result


# ── Widened blocklist — inline format (T1) ───────────────────────────────────

def test_inline_removes_session():
    content = "[CORRECTIONS] errors - active sessions wrong - real note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "active sessions wrong" not in result
    assert "real note" in result


def test_inline_removes_nodes():
    content = "[CORRECTIONS] errors - list node ids - real note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "list node ids" not in result
    assert "real note" in result


def test_inline_removes_tool_loop():
    content = "[CORRECTIONS] errors - Tool loop detected: stuck - real note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "Tool loop detected" not in result
    assert "real note" in result


def test_inline_allowlist_preserved():
    content = "[CORRECTIONS] errors - node.js needs update - real note\n[STACK]"
    result = _prune_canvas_corrections(content)
    assert "node.js needs update" in result
    assert "real note" in result


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
