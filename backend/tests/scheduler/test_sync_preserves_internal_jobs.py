"""Lock S2: sync_schedules must never remove the internal __*__ jobs.

sync_schedules computes stale jobs as `existing - active_ids`, where active_ids
is only ScheduledPrompt rows. The internal jobs (__sync__, __compact_memory__,
__canvas_reconcile__, __backup__) are not DB rows, so without the __*__ guard
they fall into "stale" and sync deletes itself + the rest on its first fire.
"""
from unittest.mock import MagicMock

import pytest

pytest.importorskip("apscheduler")  # host has no apscheduler; runs in-container

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402

import services.scheduler_worker as sw  # noqa: E402

pytestmark = pytest.mark.asyncio

INTERNAL = ["__sync__", "__compact_memory__", "__canvas_reconcile__", "__backup__"]


async def _noop():
    pass


def _fake_session_local(schedules):
    """Return an AsyncSessionLocal stand-in whose query yields `schedules`."""
    class _FakeDB:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, _query):
            r = MagicMock()
            r.scalars.return_value.all.return_value = schedules
            return r

    return lambda: _FakeDB()


def _scheduler_with_internal_jobs():
    s = AsyncIOScheduler(timezone="UTC")
    for jid in INTERNAL:
        s.add_job(_noop, "interval", hours=6, id=jid)
    return s


async def test_internal_jobs_survive_sync(monkeypatch):
    """No user schedules → sync must keep all four internal jobs."""
    monkeypatch.setattr(sw, "AsyncSessionLocal", _fake_session_local([]))
    s = _scheduler_with_internal_jobs()

    await sw.sync_schedules(s)

    assert sorted(j.id for j in s.get_jobs()) == sorted(INTERNAL)


async def test_stale_user_job_still_removed(monkeypatch):
    """The stale-removal logic still works for real (non-internal) jobs."""
    monkeypatch.setattr(sw, "AsyncSessionLocal", _fake_session_local([]))
    s = _scheduler_with_internal_jobs()
    s.add_job(_noop, "interval", hours=6, id="11111111-2222-3333-4444-555555555555")

    await sw.sync_schedules(s)

    ids = {j.id for j in s.get_jobs()}
    assert ids == set(INTERNAL)          # internals kept
    assert "11111111-2222-3333-4444-555555555555" not in ids  # stale user job gone
