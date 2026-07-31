"""Seed the admin/user/demo accounts. Idempotent — safe to re-run.

Passwords are NEVER hardcoded. Each seed user's password comes from an env var
(SEED_ADMIN_PASSWORD / SEED_USER_PASSWORD / SEED_DEMO_PASSWORD); if unset, a
random one is generated with `secrets` and printed ONCE. Existing users are
left untouched (skipped) — this script must never clobber a rotated password
or an already-set cost cap.

The canonical credential store lives OUTSIDE the repo tree
(~/.config/nim-gateway/credentials, mode 600). This script does not read,
write, or print that file's contents, and never writes credentials anywhere
inside the repo — copy the printed password out by hand.
"""
import asyncio
import os
import secrets

from sqlalchemy import select

from auth.security import hash_password
from core.db import AsyncSessionLocal, init_db
from models import User

# username -> (env var for its password, admin/user role, cost_limit_usd, cost_window_days)
_SEED_USERS = {
    "admin": ("SEED_ADMIN_PASSWORD", "admin", 25.0, 30),
    "user":  ("SEED_USER_PASSWORD",  "user",   5.0, 30),
    "demo":  ("SEED_DEMO_PASSWORD",  "user",   1.0, 30),
}


def _password_for(username: str, env_var: str) -> tuple[str, bool]:
    """Returns (password, was_generated)."""
    env_val = os.getenv(env_var)
    if env_val:
        return env_val, False
    return secrets.token_urlsafe(15), True  # ~20 chars


async def seed():
    await init_db()

    generated: dict[str, str] = {}

    async with AsyncSessionLocal() as db:
        for username, (env_var, role, cost_limit_usd, cost_window_days) in _SEED_USERS.items():
            existing = await db.scalar(select(User).where(User.username == username))
            if existing:
                print(f"[create_user] '{username}' already exists — skipped (password + cost cap untouched).")
                continue

            password, was_generated = _password_for(username, env_var)
            if was_generated:
                generated[username] = password

            db.add(User(
                username=username,
                hashed_password=hash_password(password),
                role=role,
                cost_limit_usd=cost_limit_usd,
                cost_window_days=cost_window_days,
            ))
            print(f"[create_user] queued '{username}' (role={role}, cost_limit_usd={cost_limit_usd}, "
                  f"cost_window_days={cost_window_days}).")

        await db.commit()

    if generated:
        print("\n[create_user] Generated passwords — shown ONCE, not stored anywhere by this script:")
        for username, password in generated.items():
            print(f"  {username}: {password}")
        print(
            "\n[create_user] Copy these out now. The canonical credential store is OUTSIDE this repo "
            "(~/.config/nim-gateway/credentials, mode 600) — put them there by hand. Never commit "
            "credentials into the repo tree."
        )

    print("\n[create_user] Done.")


if __name__ == "__main__":
    asyncio.run(seed())
