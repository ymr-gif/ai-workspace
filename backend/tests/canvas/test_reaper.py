"""reconcile_canvas coverage (I1 reaper + H3/H6 duplicate collapse)."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

import agent.canvas_graph as cg

pytestmark = pytest.mark.asyncio


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeExecResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalars(self._items)


async def test_reaper_prunes_malformed_and_dead_keeps_valid(monkeypatch):
    live_conv = uuid.uuid4()
    dead_conv = uuid.uuid4()

    sessions = [
        {"node_id": "prot",  "protected": True,  "config": {"conversation_id": str(uuid.uuid4())}},
        {"node_id": "bad",   "protected": False, "config": {"conversation_id": "test"}},          # malformed
        {"node_id": "dead",  "protected": False, "config": {"conversation_id": str(dead_conv)}},  # no pg row
        {"node_id": "live",  "protected": False, "config": {"conversation_id": str(live_conv)}},  # real
    ]
    monkeypatch.setattr(cg, "find_nodes", AsyncMock(return_value=sessions))
    pruned = []
    monkeypatch.setattr(cg, "delete_node", AsyncMock(side_effect=lambda uid, nid: pruned.append(nid)))

    db = MagicMock()
    db.execute = AsyncMock(return_value=_FakeExecResult([live_conv]))  # only live_conv exists

    await cg._reap_orphan_sessions(1, db)

    assert set(pruned) == {"bad", "dead"}
    assert "prot" not in pruned and "live" not in pruned


async def test_collapse_duplicate_inputs_and_sessions(monkeypatch):
    """H3/H6: duplicate singleton inputs + same-conv sessions collapse to one,
    always keeping the protected node."""
    conv = str(uuid.uuid4())

    def fake_find(uid, node_type):
        if node_type == "input":
            return [
                {"node_id": "in-keep", "protected": True,  "config": {}},
                {"node_id": "in-dup",  "protected": False, "config": {}},
            ]
        if node_type == "session":
            return [
                {"node_id": "ses-keep", "protected": True,  "config": {"conversation_id": conv}},
                {"node_id": "ses-dup",  "protected": False, "config": {"conversation_id": conv}},
            ]
        return []  # memory/config — none

    monkeypatch.setattr(cg, "find_nodes", AsyncMock(side_effect=fake_find))
    pruned = []
    monkeypatch.setattr(cg, "delete_node", AsyncMock(side_effect=lambda uid, nid: pruned.append(nid)))

    await cg._collapse_duplicate_nodes(1)

    assert set(pruned) == {"in-dup", "ses-dup"}      # protected ones kept
    assert "in-keep" not in pruned and "ses-keep" not in pruned


async def test_collapse_force_deletes_both_protected_duplicate(monkeypatch):
    """H5: when a *duplicate* core is itself protected, collapse unprotects it and
    removes it — keeping exactly one, never leaving a stuck protected dup."""
    protected = {"in-keep": True, "in-dup": True}   # both protected

    def fake_find(uid, node_type):
        if node_type == "input":
            return [
                {"node_id": "in-keep", "protected": True, "config": {}},
                {"node_id": "in-dup",  "protected": True, "config": {}},
            ]
        return []

    pruned = []

    async def fake_delete(uid, nid):
        if protected.get(nid):                       # delete_node refuses protected
            raise ValueError(f"Cannot delete core node {nid}")
        pruned.append(nid)

    async def fake_set_protected(uid, nid, value=True):
        protected[nid] = value

    monkeypatch.setattr(cg, "find_nodes", AsyncMock(side_effect=fake_find))
    monkeypatch.setattr(cg, "delete_node", AsyncMock(side_effect=fake_delete))
    monkeypatch.setattr(cg, "set_protected", AsyncMock(side_effect=fake_set_protected))

    await cg._collapse_duplicate_nodes(1)

    assert pruned == ["in-dup"]                       # the extra protected dup removed
    assert protected["in-keep"] is True              # kept node still protected
