"""create_node guard coverage (I2 + B6 + UUID hardening)."""
import uuid

import pytest

import agent.canvas_graph as cg
from tests.canvas.conftest import make_driver

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("node_type", ["insights", "goals", "automations", "mech"])
async def test_embedded_types_rejected(node_type):
    """B6: the 4 embedded types are never standalone nodes."""
    with pytest.raises(ValueError, match="not a standalone canvas node"):
        await cg.create_node(1, node_type)


@pytest.mark.parametrize("node_type", ["input", "session", "memory", "config"])
async def test_managed_types_rejected_for_ai(node_type):
    """I2/H1: AI/REST path (internal=False) may not create managed core nodes."""
    with pytest.raises(ValueError, match="managed automatically"):
        await cg.create_node(1, node_type)


async def test_unknown_type_rejected():
    with pytest.raises(ValueError, match="Unknown node type"):
        await cg.create_node(1, "not_a_real_type")


async def test_malformed_conversation_id_rejected():
    """I2 hardening: a non-UUID conversation_id can never resolve to a real conv."""
    with pytest.raises(ValueError, match="Invalid conversation_id"):
        await cg.create_node(1, "session", {"conversation_id": "d3c4b1a2-not-a-uuid-xyz"}, internal=True)


async def test_internal_permanent_create_passes_guard(monkeypatch):
    """I2: internal=True bootstrap may create a permanent node (proves the guard
    lets it through — it reaches the driver instead of raising ValueError)."""
    captured = {}

    def handler(query, params):
        captured["query"] = query
        from tests.canvas.conftest import FakeResult
        return FakeResult()

    monkeypatch.setattr(cg, "get_driver", lambda: make_driver(handler))
    monkeypatch.setattr(cg, "_cache_del", _noop)

    valid_conv = str(uuid.uuid4())
    node_id = await cg.create_node(1, "session", {"conversation_id": valid_conv}, internal=True)
    uuid.UUID(node_id)                       # returns a real node id
    assert "CREATE (n:CanvasNode" in captured["query"]


async def test_dedup_singleton_returns_existing(monkeypatch):
    """H6: creating a second input/memory/config returns the existing node id."""
    from tests.canvas.conftest import FakeResult
    created = {"ran": False}

    def handler(query, params):
        if query.lstrip().startswith("MATCH"):                       # find_nodes
            return FakeResult(records=[{"n": {"node_id": "existing-input", "config": "{}"}}])
        created["ran"] = True                                        # CREATE — must not happen
        return FakeResult()

    monkeypatch.setattr(cg, "get_driver", lambda: make_driver(handler))
    monkeypatch.setattr(cg, "_cache_del", _noop)

    node_id = await cg.create_node(1, "input", {}, internal=True)
    assert node_id == "existing-input"
    assert created["ran"] is False                                   # no duplicate created


async def test_dedup_session_by_conversation_id(monkeypatch):
    """H6: a session for an already-mapped conversation_id returns the existing node."""
    from tests.canvas.conftest import FakeResult
    conv = str(uuid.uuid4())
    created = {"ran": False}

    def handler(query, params):
        if query.lstrip().startswith("MATCH"):
            return FakeResult(records=[{"n": {"node_id": "existing-session",
                                              "config": f'{{"conversation_id": "{conv}"}}'}}])
        created["ran"] = True
        return FakeResult()

    monkeypatch.setattr(cg, "get_driver", lambda: make_driver(handler))
    monkeypatch.setattr(cg, "_cache_del", _noop)

    node_id = await cg.create_node(1, "session", {"conversation_id": conv}, internal=True)
    assert node_id == "existing-session"
    assert created["ran"] is False


async def _noop(*a, **k):
    return None
