"""Ephemeral per-login demo accounts (services/demo.py + login()/_check_cost_cap
wiring). Unit tier — mocked DB (AsyncMock) + mocked Redis, no live NIM, no live
Postgres/Redis/Neo4j.

Covers: is_ephemeral_demo prefix logic; pool_spend_usd (query + Redis cache);
count_live_demo_accounts; mint_ephemeral_demo; reap_idle_demos (idle vs active,
created_at fallback); login() flag off (unchanged seed) / flag on (mints +
ephemeral JWT subject) / refused at pool cap; _check_cost_cap blocks an
ephemeral account past the pool cap and leaves the flag-off / non-demo paths
untouched.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import config
from fastapi import HTTPException

import auth.router as auth_router_module
from api.chat import helpers
from models import User
from services import demo as demo_svc


@pytest.fixture(autouse=True)
def _reset_config():
    config.DEMO_EPHEMERAL_ENABLED = False
    config.DEMO_SEED_USERNAME = "demo"
    config.DEMO_PER_ACCOUNT_CAP_USD = 1.0
    config.DEMO_PER_ACCOUNT_WINDOW_DAYS = 1
    config.DEMO_GLOBAL_CAP_USD = 10.0
    config.DEMO_GLOBAL_WINDOW_HOURS = 24
    config.DEMO_IDLE_TTL_HOURS = 2
    config.DEMO_REAP_INTERVAL_MIN = 30
    config.DEMO_MAX_LIVE_ACCOUNTS = 0
    config.USE_REDIS = False
    yield


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def _plain_all_result(rows):
    r = MagicMock()
    r.all.return_value = rows
    return r


class _FormData:
    def __init__(self, username, password):
        self.username = username
        self.password = password


# ── is_ephemeral_demo ────────────────────────────────────────────────────────

def test_is_ephemeral_demo_prefix():
    assert demo_svc.is_ephemeral_demo("demo_ab12cd34ef56")
    assert not demo_svc.is_ephemeral_demo("demo")           # the seed login itself
    assert not demo_svc.is_ephemeral_demo("someone_else")
    assert not demo_svc.is_ephemeral_demo("demonstration")  # prefix, not substring


# ── pool_spend_usd ───────────────────────────────────────────────────────────

async def test_pool_spend_usd_queries_db_when_redis_off():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(4.5))

    total = await demo_svc.pool_spend_usd(db)

    assert total == 4.5
    db.execute.assert_awaited_once()


async def test_pool_spend_usd_uses_redis_cache_when_enabled():
    config.USE_REDIS = True
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(999.0))  # must NOT be reached

    redis = AsyncMock()
    redis.get = AsyncMock(return_value="3.25")
    redis.set = AsyncMock()

    with patch("services.demo.get_redis", return_value=redis):
        total = await demo_svc.pool_spend_usd(db)

    assert total == 3.25
    db.execute.assert_not_awaited()


async def test_pool_spend_usd_falls_back_to_db_on_redis_miss():
    config.USE_REDIS = True
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(1.5))

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # cache miss
    redis.set = AsyncMock()

    with patch("services.demo.get_redis", return_value=redis):
        total = await demo_svc.pool_spend_usd(db)

    assert total == 1.5
    db.execute.assert_awaited_once()
    redis.set.assert_awaited_once()


# ── count_live_demo_accounts ─────────────────────────────────────────────────

async def test_count_live_demo_accounts():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(7))

    count = await demo_svc.count_live_demo_accounts(db)

    assert count == 7


# ── mint_ephemeral_demo ──────────────────────────────────────────────────────

async def test_mint_ephemeral_demo_sets_prefix_and_caps():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    config.DEMO_PER_ACCOUNT_CAP_USD = 1.0
    config.DEMO_PER_ACCOUNT_WINDOW_DAYS = 1

    user = await demo_svc.mint_ephemeral_demo(db)

    assert user.username.startswith("demo_")
    assert user.username != "demo_"          # has a random suffix
    assert user.role == "user"
    assert user.is_active is True
    assert user.cost_limit_usd == 1.0
    assert user.cost_window_days == 1
    db.add.assert_called_once_with(user)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)


async def test_mint_ephemeral_demo_never_reusable_as_direct_login():
    """The hashed password is random + discarded — no plaintext round-trips it."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    u1 = await demo_svc.mint_ephemeral_demo(db)
    u2 = await demo_svc.mint_ephemeral_demo(db)

    assert u1.username != u2.username
    assert u1.hashed_password != u2.hashed_password


# ── reap_idle_demos ──────────────────────────────────────────────────────────

async def test_reap_idle_demos_selects_only_idle_skips_active():
    now = datetime.now(timezone.utc)
    idle_user = User(id=1, username="demo_idle00000001", hashed_password="x",
                      created_at=now - timedelta(hours=5))
    active_user = User(id=2, username="demo_active000002", hashed_password="x",
                        created_at=now - timedelta(hours=5))

    rows = [
        (idle_user, now - timedelta(hours=3)),      # last msg 3h ago, TTL=2h -> idle
        (active_user, now - timedelta(minutes=5)),  # last msg 5m ago -> still active
    ]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_plain_all_result(rows))

    with patch.object(demo_svc, "_purge_demo_user", AsyncMock()) as purge:
        count = await demo_svc.reap_idle_demos(db)

    assert count == 1
    purge.assert_awaited_once_with(db, 1)


async def test_reap_idle_demos_falls_back_to_created_at_when_no_messages():
    now = datetime.now(timezone.utc)
    never_messaged = User(id=3, username="demo_nomsg0000003", hashed_password="x",
                           created_at=now - timedelta(hours=10))

    rows = [(never_messaged, None)]  # no MAX(Message.created_at) row -> use created_at

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_plain_all_result(rows))

    with patch.object(demo_svc, "_purge_demo_user", AsyncMock()) as purge:
        count = await demo_svc.reap_idle_demos(db)

    assert count == 1
    purge.assert_awaited_once_with(db, 3)


async def test_reap_idle_demos_no_purge_when_nothing_idle():
    now = datetime.now(timezone.utc)
    fresh_user = User(id=4, username="demo_fresh0000004", hashed_password="x",
                       created_at=now)
    rows = [(fresh_user, now - timedelta(minutes=1))]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_plain_all_result(rows))

    with patch.object(demo_svc, "_purge_demo_user", AsyncMock()) as purge:
        count = await demo_svc.reap_idle_demos(db)

    assert count == 0
    purge.assert_not_awaited()


# ── login() wiring ───────────────────────────────────────────────────────────

async def test_login_flag_off_returns_seed_unchanged():
    config.DEMO_EPHEMERAL_ENABLED = False
    seed_user = User(id=10, username="demo", hashed_password="x", role="user", is_active=True)
    db = AsyncMock()
    mock_cat = MagicMock(return_value="tok")

    with patch("auth.router.authenticate_user", AsyncMock(return_value=seed_user)), \
         patch("auth.router.create_access_token", mock_cat), \
         patch("auth.router.mint_ephemeral_demo", AsyncMock()) as mint:
        token = await auth_router_module.login(_FormData("demo", "eidetic-demo"), db)

    mint.assert_not_awaited()
    assert token.access_token == "tok"
    assert mock_cat.call_args[0][0]["sub"] == "demo"


async def test_login_flag_on_mints_ephemeral_with_distinct_subject():
    config.DEMO_EPHEMERAL_ENABLED = True
    config.DEMO_SEED_USERNAME = "demo"
    seed_user = User(id=10, username="demo", hashed_password="x", role="user", is_active=True)
    minted = User(id=99, username="demo_abcdef123456", hashed_password="y", role="user", is_active=True)
    db = AsyncMock()
    mock_cat = MagicMock(return_value="tok")

    with patch("auth.router.authenticate_user", AsyncMock(return_value=seed_user)), \
         patch("auth.router.pool_spend_usd", AsyncMock(return_value=0.0)), \
         patch("auth.router.mint_ephemeral_demo", AsyncMock(return_value=minted)) as mint, \
         patch("auth.router.create_access_token", mock_cat):
        token = await auth_router_module.login(_FormData("demo", "eidetic-demo"), db)

    mint.assert_awaited_once()
    assert token.access_token == "tok"
    assert mock_cat.call_args[0][0]["sub"] == "demo_abcdef123456"


async def test_login_two_mints_yield_two_distinct_subjects():
    """Two logins a few minutes apart -> two independent sandboxes."""
    config.DEMO_EPHEMERAL_ENABLED = True
    seed_user = User(id=10, username="demo", hashed_password="x", role="user", is_active=True)
    minted_a = User(id=101, username="demo_aaaaaaaaaaaa", hashed_password="y", role="user", is_active=True)
    minted_b = User(id=102, username="demo_bbbbbbbbbbbb", hashed_password="z", role="user", is_active=True)
    db = AsyncMock()
    subjects = []

    def _capture(data, expires_delta=None):
        subjects.append(data["sub"])
        return "tok"

    with patch("auth.router.authenticate_user", AsyncMock(return_value=seed_user)), \
         patch("auth.router.pool_spend_usd", AsyncMock(return_value=0.0)), \
         patch("auth.router.mint_ephemeral_demo", AsyncMock(side_effect=[minted_a, minted_b])), \
         patch("auth.router.create_access_token", side_effect=_capture):
        await auth_router_module.login(_FormData("demo", "eidetic-demo"), db)
        await auth_router_module.login(_FormData("demo", "eidetic-demo"), db)

    assert subjects == ["demo_aaaaaaaaaaaa", "demo_bbbbbbbbbbbb"]
    assert subjects[0] != subjects[1]


async def test_login_refused_at_pool_cap():
    config.DEMO_EPHEMERAL_ENABLED = True
    config.DEMO_GLOBAL_CAP_USD = 10.0
    seed_user = User(id=10, username="demo", hashed_password="x", role="user", is_active=True)
    db = AsyncMock()

    with patch("auth.router.authenticate_user", AsyncMock(return_value=seed_user)), \
         patch("auth.router.pool_spend_usd", AsyncMock(return_value=10.0)), \
         patch("auth.router.mint_ephemeral_demo", AsyncMock()) as mint:
        with pytest.raises(HTTPException) as exc:
            await auth_router_module.login(_FormData("demo", "eidetic-demo"), db)

    assert exc.value.status_code == 503
    mint.assert_not_awaited()


async def test_login_refused_at_max_live_accounts():
    config.DEMO_EPHEMERAL_ENABLED = True
    config.DEMO_GLOBAL_CAP_USD = 10.0
    config.DEMO_MAX_LIVE_ACCOUNTS = 5
    seed_user = User(id=10, username="demo", hashed_password="x", role="user", is_active=True)
    db = AsyncMock()

    with patch("auth.router.authenticate_user", AsyncMock(return_value=seed_user)), \
         patch("auth.router.pool_spend_usd", AsyncMock(return_value=0.0)), \
         patch("auth.router.count_live_demo_accounts", AsyncMock(return_value=5)), \
         patch("auth.router.mint_ephemeral_demo", AsyncMock()) as mint:
        with pytest.raises(HTTPException) as exc:
            await auth_router_module.login(_FormData("demo", "eidetic-demo"), db)

    assert exc.value.status_code == 503
    mint.assert_not_awaited()


async def test_login_flag_on_non_seed_user_unchanged():
    """Flag on but logging in as a regular (non-seed) account -> no mint."""
    config.DEMO_EPHEMERAL_ENABLED = True
    regular_user = User(id=20, username="user", hashed_password="x", role="user", is_active=True)
    db = AsyncMock()
    mock_cat = MagicMock(return_value="tok")

    with patch("auth.router.authenticate_user", AsyncMock(return_value=regular_user)), \
         patch("auth.router.create_access_token", mock_cat), \
         patch("auth.router.mint_ephemeral_demo", AsyncMock()) as mint:
        token = await auth_router_module.login(_FormData("user", "user-secret"), db)

    mint.assert_not_awaited()
    assert mock_cat.call_args[0][0]["sub"] == "user"


# ── _check_cost_cap ephemeral pool enforcement ───────────────────────────────

async def test_check_cost_cap_blocks_ephemeral_past_pool():
    config.DEMO_EPHEMERAL_ENABLED = True
    config.DEMO_GLOBAL_CAP_USD = 10.0
    user = User(id=5, username="demo_abcdef123456", hashed_password="x", cost_limit_usd=None)
    db = AsyncMock()

    with patch("api.chat.helpers.pool_spend_usd", AsyncMock(return_value=10.0)):
        with pytest.raises(HTTPException) as exc:
            await helpers._check_cost_cap(user, db)

    assert exc.value.status_code == 402


async def test_check_cost_cap_allows_ephemeral_under_pool():
    config.DEMO_EPHEMERAL_ENABLED = True
    config.DEMO_GLOBAL_CAP_USD = 10.0
    user = User(id=5, username="demo_abcdef123456", hashed_password="x", cost_limit_usd=None)
    db = AsyncMock()

    with patch("api.chat.helpers.pool_spend_usd", AsyncMock(return_value=2.0)):
        await helpers._check_cost_cap(user, db)  # must not raise


async def test_check_cost_cap_flag_off_skips_pool_check_entirely():
    config.DEMO_EPHEMERAL_ENABLED = False
    user = User(id=5, username="demo_abcdef123456", hashed_password="x", cost_limit_usd=None)
    db = AsyncMock()
    pool_mock = AsyncMock(return_value=999.0)

    with patch("api.chat.helpers.pool_spend_usd", pool_mock):
        await helpers._check_cost_cap(user, db)  # cost_limit_usd None -> early return

    pool_mock.assert_not_awaited()


async def test_check_cost_cap_non_demo_user_skips_pool_check():
    config.DEMO_EPHEMERAL_ENABLED = True
    user = User(id=6, username="user", hashed_password="x", cost_limit_usd=None)
    db = AsyncMock()
    pool_mock = AsyncMock(return_value=999.0)

    with patch("api.chat.helpers.pool_spend_usd", pool_mock):
        await helpers._check_cost_cap(user, db)  # not ephemeral -> pool never consulted

    pool_mock.assert_not_awaited()


async def test_check_cost_cap_per_account_cap_still_enforced_for_ephemeral():
    """Per-account cost_limit_usd path stays unchanged even under the pool gate."""
    config.DEMO_EPHEMERAL_ENABLED = True
    config.DEMO_GLOBAL_CAP_USD = 10.0
    user = User(id=5, username="demo_abcdef123456", hashed_password="x",
                cost_limit_usd=1.0, cost_window_days=None)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar_result(1.5))  # over the $1 per-account cap

    with patch("api.chat.helpers.pool_spend_usd", AsyncMock(return_value=0.0)):
        with pytest.raises(HTTPException) as exc:
            await helpers._check_cost_cap(user, db)

    assert exc.value.status_code == 402
    assert "Cost cap reached" in exc.value.detail
