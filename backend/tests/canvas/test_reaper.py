"""_reap_orphan_sessions coverage (I1)."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

import api.canvas as canvas

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
    keep_id = "keep-node"
    live_conv = uuid.uuid4()
    dead_conv = uuid.uuid4()

    sessions = [
        {"node_id": keep_id,  "protected": False, "config": {"conversation_id": str(uuid.uuid4())}},
        {"node_id": "prot",   "protected": True,  "config": {"conversation_id": str(uuid.uuid4())}},
        {"node_id": "bad",    "protected": False, "config": {"conversation_id": "test"}},          # malformed
        {"node_id": "dead",   "protected": False, "config": {"conversation_id": str(dead_conv)}},  # no pg row
        {"node_id": "live",   "protected": False, "config": {"conversation_id": str(live_conv)}},  # real
    ]

    monkeypatch.setattr(canvas, "find_nodes", AsyncMock(return_value=sessions))
    pruned = []
    async def _fake_delete(uid, nid):
        pruned.append(nid)
    monkeypatch.setattr(canvas, "delete_node", AsyncMock(side_effect=_fake_delete))

    db = MagicMock()
    db.execute = AsyncMock(return_value=_FakeExecResult([live_conv]))  # only live_conv exists

    await canvas._reap_orphan_sessions(1, db, keep_node_id=keep_id)

    assert set(pruned) == {"bad", "dead"}      # malformed + dead pruned
    assert "prot" not in pruned                # protected skipped
    assert keep_id not in pruned               # global session skipped
    assert "live" not in pruned                # valid session kept


async def test_reaper_noop_when_all_valid(monkeypatch):
    live_conv = uuid.uuid4()
    sessions = [
        {"node_id": "live", "protected": False, "config": {"conversation_id": str(live_conv)}},
    ]
    monkeypatch.setattr(canvas, "find_nodes", AsyncMock(return_value=sessions))
    delete_mock = AsyncMock()
    monkeypatch.setattr(canvas, "delete_node", delete_mock)

    db = MagicMock()
    db.execute = AsyncMock(return_value=_FakeExecResult([live_conv]))

    await canvas._reap_orphan_sessions(1, db, keep_node_id="other")
    delete_mock.assert_not_called()
