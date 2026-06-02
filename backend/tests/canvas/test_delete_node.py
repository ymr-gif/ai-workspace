"""delete_node guard coverage (G1 protection + F2 no-match)."""
import pytest

import agent.canvas_graph as cg
from tests.canvas.conftest import FakeResult, make_driver

pytestmark = pytest.mark.asyncio


async def _noop(*a, **k):
    return None


async def test_protected_node_refused(monkeypatch):
    """G1: a protected core node cannot be deleted."""
    def handler(query, params):
        if "coalesce(n.protected" in query:           # protection pre-check
            return FakeResult(records=[{"protected": True}])
        return FakeResult(nodes_deleted=1)

    monkeypatch.setattr(cg, "get_driver", lambda: make_driver(handler))
    monkeypatch.setattr(cg, "_cache_del", _noop)

    with pytest.raises(ValueError, match="Cannot delete core node"):
        await cg.delete_node(1, "some-protected-id")


async def test_missing_node_raises(monkeypatch):
    """F2: deleting a non-existent id surfaces an error (no false success)."""
    def handler(query, params):
        if "coalesce(n.protected" in query:
            return FakeResult(records=[])              # no such node
        return FakeResult(nodes_deleted=0)

    monkeypatch.setattr(cg, "get_driver", lambda: make_driver(handler))
    monkeypatch.setattr(cg, "_cache_del", _noop)

    with pytest.raises(ValueError, match="not found"):
        await cg.delete_node(1, "does-not-exist")


async def test_unprotected_node_deletes(monkeypatch):
    """Normal path: an unprotected, existing node is deleted without raising."""
    def handler(query, params):
        if "coalesce(n.protected" in query:
            return FakeResult(records=[{"protected": False}])
        return FakeResult(nodes_deleted=1)

    monkeypatch.setattr(cg, "get_driver", lambda: make_driver(handler))
    monkeypatch.setattr(cg, "_cache_del", _noop)

    await cg.delete_node(1, "a-real-id")               # must not raise
