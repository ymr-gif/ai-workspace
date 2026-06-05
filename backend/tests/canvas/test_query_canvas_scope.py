"""query_canvas auto-scoping coverage (B / J2).

The 70B frequently omits the {user_id: $uid} filter. query_canvas now injects
it into a bare (var:CanvasNode) pattern; complex/ambiguous queries still error.
"""
import pytest

import agent.canvas_graph as cg
from tests.canvas.conftest import FakeResult, make_driver

pytestmark = pytest.mark.asyncio


def _capture_driver(captured):
    def handler(query, params):
        captured["cypher"] = query
        captured["params"] = params
        return FakeResult(records=[{"n": {}}])
    return make_driver(handler)


async def test_autoscopes_bare_pattern(monkeypatch):
    """MATCH (n:CanvasNode) RETURN n -> injects {user_id: $uid} and runs."""
    captured = {}
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver(captured))

    await cg.query_canvas(7, "MATCH (n:CanvasNode) RETURN n")

    assert "{user_id: $uid}" in captured["cypher"]
    assert captured["params"]["uid"] == 7


async def test_autoscopes_no_var(monkeypatch):
    """A var-less (:CanvasNode) pattern is also scoped."""
    captured = {}
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver(captured))

    await cg.query_canvas(1, "MATCH (:CanvasNode) RETURN count(*)")

    assert ":CanvasNode {user_id: $uid}" in captured["cypher"]


async def test_explicit_scope_passthrough(monkeypatch):
    """Already-scoped queries are left untouched."""
    captured = {}
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver(captured))

    original = "MATCH (n:CanvasNode {user_id: $uid}) WHERE n.node_type='session' RETURN n"
    await cg.query_canvas(2, original)

    assert captured["cypher"] == original


async def test_propertied_but_unscoped_errors(monkeypatch):
    """A propertied label without user_id is rejected (can't be auto-fixed)."""
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver({}))

    with pytest.raises(ValueError, match="must be scoped"):
        await cg.query_canvas(3, "MATCH (n:CanvasNode {node_type:'session'}) RETURN n")


async def test_no_canvasnode_label_errors(monkeypatch):
    """A query that doesn't touch :CanvasNode is rejected."""
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver({}))

    with pytest.raises(ValueError, match=":CanvasNode nodes"):
        await cg.query_canvas(4, "MATCH (n:Foo) RETURN n")


# ── cross-tenant scoping (security review HIGH) ──────────────────────

async def test_multi_binding_all_scoped(monkeypatch):
    """Every bare CanvasNode binding is scoped — not just the first (no leak)."""
    captured = {}
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver(captured))

    await cg.query_canvas(9, "MATCH (a:CanvasNode), (b:CanvasNode) RETURN a, b")

    assert captured["cypher"].count("{user_id: $uid}") == 2


async def test_partial_scope_completed(monkeypatch):
    """A query with one scoped + one bare binding gets the bare one scoped too."""
    captured = {}
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver(captured))

    await cg.query_canvas(9, "MATCH (a:CanvasNode {user_id: $uid}), (b:CanvasNode) RETURN a, b")

    assert captured["cypher"].count("{user_id: $uid}") == 2


async def test_literal_cross_user_rejected(monkeypatch):
    """A literal foreign user_id ({user_id: 999}) is rejected — no cross-tenant read."""
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver({}))

    with pytest.raises(ValueError, match="must be scoped"):
        await cg.query_canvas(10, "MATCH (n:CanvasNode {user_id: 999}) RETURN n")


async def test_unscoped_second_label_rejected(monkeypatch):
    """A propertied (non-bare) unscoped second binding is rejected, not silently run."""
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver({}))

    with pytest.raises(ValueError, match="must be scoped"):
        await cg.query_canvas(
            11,
            "MATCH (a:CanvasNode {user_id: $uid}), (b:CanvasNode {user_id: 999}) RETURN a, b",
        )


async def test_scoped_with_extra_props_ok(monkeypatch):
    """{user_id: $uid, ...extra} passes (extra filters allowed after the scope)."""
    captured = {}
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver(captured))

    q = "MATCH (n:CanvasNode {user_id: $uid, node_type: 'session'}) RETURN n"
    await cg.query_canvas(12, q)
    assert captured["cypher"] == q


async def test_where_not_uid_is_neutralised(monkeypatch):
    """A bare match with a hostile WHERE still gets the authoritative pattern scope."""
    captured = {}
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver(captured))

    await cg.query_canvas(13, "MATCH (n:CanvasNode) WHERE n.user_id <> $uid RETURN n")
    # pattern map {user_id: $uid} is injected and is authoritative (a WHERE
    # cannot widen it) -> the query is forced to the caller's own rows.
    assert "{user_id: $uid}" in captured["cypher"]


async def test_write_keyword_blocked(monkeypatch):
    """Write operations remain forbidden in query_canvas."""
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver({}))

    with pytest.raises(ValueError, match="not allowed"):
        await cg.query_canvas(5, "DELETE (n:CanvasNode {user_id: $uid})")


async def test_write_keyword_mid_query_blocked(monkeypatch):
    """A write clause that isn't the first word is still rejected (read-only)."""
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver({}))

    with pytest.raises(ValueError, match="not allowed"):
        await cg.query_canvas(6, "MATCH (n:CanvasNode {user_id: $uid}) DETACH DELETE n")


async def test_read_property_not_false_flagged(monkeypatch):
    """Property names containing a keyword substring (created_at) are NOT blocked."""
    captured = {}
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver(captured))

    await cg.query_canvas(8, "MATCH (n:CanvasNode {user_id: $uid}) RETURN n.created_at")
    assert "created_at" in captured["cypher"]
