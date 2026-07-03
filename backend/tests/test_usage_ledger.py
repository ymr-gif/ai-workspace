"""Unit tests for the stateless-endpoint usage ledger (QUEUE Q4).

No DB/NIM — pure calc tests + a mocked-session ledger-row test.
Run: pytest tests/test_usage_ledger.py -q
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.chat.usage_ledger import LEDGER_TITLE, record_stateless_usage, tokens_and_cost
from config import MODEL_PRICING, MODELS


LLAMA = MODELS["llama"]


def test_tokens_and_cost_uses_nim_usage():
    usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    pt, ct, tt, cost, est = tokens_and_cost(usage, "x", "y", LLAMA)
    assert (pt, ct, tt) == (100, 50, 150)
    assert est is False
    pricing = MODEL_PRICING[LLAMA]
    assert cost == pytest.approx(100 / 1e6 * pricing["input"] + 50 / 1e6 * pricing["output"])


def test_tokens_and_cost_estimates_without_usage():
    pt, ct, tt, cost, est = tokens_and_cost(None, "a" * 40, "b" * 80, LLAMA)
    assert (pt, ct, tt) == (10, 20, 30)   # len // 4 heuristic
    assert est is True
    assert cost > 0


def test_tokens_and_cost_unknown_model_zero_cost():
    _, _, _, cost, _ = tokens_and_cost({"prompt_tokens": 10, "completion_tokens": 10}, "", "", "bogus/model")
    assert cost == 0.0


@pytest.mark.asyncio
async def test_record_writes_assistant_row_in_ledger_conv():
    db = MagicMock()
    existing_conv = MagicMock()
    existing_conv.id = "conv-id"
    scalars = MagicMock()
    scalars.first.return_value = existing_conv
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=exec_result)
    db.commit = AsyncMock()
    db.add = MagicMock()

    await record_stateless_usage(
        db, 1, endpoint="/chat", model=LLAMA, prompt_text="hi", response_text="yo",
        usage={"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
    )
    db.commit.assert_awaited()
    msg = db.add.call_args[0][0]
    assert msg.role == "assistant"
    assert msg.conversation_id == "conv-id"
    assert msg.total_tokens == 12
    assert msg.cost_usd > 0
    assert LEDGER_TITLE  # exported for live verification


@pytest.mark.asyncio
async def test_record_never_raises_on_db_failure():
    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))
    db.rollback = AsyncMock()
    await record_stateless_usage(
        db, 1, endpoint="/chat", model=LLAMA, prompt_text="hi", response_text="yo", usage=None,
    )   # must not raise
    db.rollback.assert_awaited()
