"""Regression guard: _ensure_creation_wiring must create the session node via the
internal=True bootstrap path, or the I2 permanent-type guard silently blocks it
(create_conversation would commit a Postgres row but never show a canvas node)."""
from unittest.mock import AsyncMock

import pytest

import llm.tools.executor as executor

pytestmark = pytest.mark.asyncio


async def test_creation_wiring_uses_internal_create(monkeypatch):
    # no existing session node → must create; input node already exists
    monkeypatch.setattr(executor, "find_nodes", AsyncMock(side_effect=[
        [],                            # find_nodes("session") → none
        [{"node_id": "input-1"}],      # find_nodes("input")   → exists
    ]))
    create_mock = AsyncMock(return_value="new-session-node")
    monkeypatch.setattr(executor, "create_node", create_mock)
    monkeypatch.setattr(executor, "get_canvas_graph", AsyncMock(return_value={"wires": []}))
    monkeypatch.setattr(executor, "wire_nodes", AsyncMock())

    conv_id = "00000000-0000-0000-0000-000000000001"
    await executor._ensure_creation_wiring(1, conv_id, "session", {"conversation_id": conv_id})

    create_mock.assert_awaited_once()
    # the critical assertion: internal=True, or I2 blocks the session create
    assert create_mock.await_args.kwargs.get("internal") is True
