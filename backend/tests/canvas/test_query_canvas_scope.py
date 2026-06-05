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


async def test_complex_unscopable_errors(monkeypatch):
    """A propertied label with no bare pattern and no $uid -> instructive error."""
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver({}))

    with pytest.raises(ValueError, match="scope to the current user"):
        await cg.query_canvas(3, "MATCH (n:CanvasNode {node_type:'session'}) RETURN n")


async def test_no_canvasnode_label_errors(monkeypatch):
    """A query that doesn't touch :CanvasNode is rejected."""
    monkeypatch.setattr(cg, "get_driver", lambda: _capture_driver({}))

    with pytest.raises(ValueError, match="scope to the current user"):
        await cg.query_canvas(4, "MATCH (n:Foo) RETURN n")


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
