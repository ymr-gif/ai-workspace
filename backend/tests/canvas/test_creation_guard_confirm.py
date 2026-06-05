"""Creation-guard Layer 3 confirmation (_user_confirmed_latest).

Regression cover: the confirm check must not depend on a short message window
or a literal ask string — when `pending`, the latest user message is the reply.
A title, a bare "yes", etc. confirm; negations and questions stay pending.
"""
import uuid
from unittest.mock import MagicMock

import pytest

import llm.tools.executor as ex

pytestmark = pytest.mark.asyncio


class _Msg:
    def __init__(self, content):
        self.content = content
        self.role = "user"


class _Result:
    def __init__(self, msg):
        self._msg = msg

    def scalars(self):
        s = MagicMock()
        s.first.return_value = self._msg
        return s


class _DB:
    """Minimal async stand-in: db.execute(...) -> result with the latest msg."""
    def __init__(self, msg):
        self._msg = msg

    async def execute(self, *a, **k):
        return _Result(self._msg)


async def _confirm(content):
    db = _DB(_Msg(content) if content is not None else None)
    return await ex._user_confirmed_latest(db, uuid.uuid4())


async def test_bare_title_confirms():
    assert await _confirm("TEST") is True
    assert await _confirm("title would be TEST") is True


async def test_affirmative_confirms():
    assert await _confirm("yes") is True
    assert await _confirm("yes, please create it") is True


async def test_negation_holds():
    assert await _confirm("cancel") is False
    assert await _confirm("never mind") is False
    assert await _confirm("don't create it") is False


async def test_question_holds():
    assert await _confirm("what nodes are on my canvas?") is False
    assert await _confirm("can you make a new session for me?") is False


async def test_empty_or_missing_holds():
    assert await _confirm("") is False
    assert await _confirm("   ") is False
    assert await _confirm(None) is False
