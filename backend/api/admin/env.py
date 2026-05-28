import os
from pathlib import Path

from dotenv import dotenv_values, find_dotenv, set_key
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_current_user, require_role
from core.db import get_db
from models import User

from .utils import _audit, _mask

ENV_PATH = Path(find_dotenv() or ".env")

router = APIRouter()


class EnvUpdateRequest(BaseModel):
    value: str


@router.get("/env")
async def list_env(
    admin: User = Depends(require_role("admin")),
):
    env = dotenv_values(ENV_PATH)
    return {
        key: _mask(key, value)
        for key, value in sorted(env.items())
    }


@router.get("/env/{key}")
async def get_env(
    key: str,
    admin: User = Depends(require_role("admin")),
):
    env = dotenv_values(ENV_PATH)
    if key not in env:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found in .env")
    value = env[key]
    return {key: _mask(key, value)}


@router.put("/env/{key}")
async def update_env(
    key: str,
    body: EnvUpdateRequest,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(require_role("admin")),
):
    env = dotenv_values(ENV_PATH)
    old_value = env.get(key, "")

    set_key(str(ENV_PATH), key, body.value, quote_mode="never")
    os.environ[key] = body.value

    import config as cfg
    if hasattr(cfg, key):
        try:
            existing = getattr(cfg, key)
            if isinstance(existing, bool):
                setattr(cfg, key, body.value.lower() in ("true", "1", "yes"))
            elif isinstance(existing, int):
                setattr(cfg, key, int(body.value))
            elif isinstance(existing, float):
                setattr(cfg, key, float(body.value))
            else:
                setattr(cfg, key, body.value)
        except (ValueError, TypeError):
            setattr(cfg, key, body.value)

    await _audit(db, admin, "env.updated", detail={
        "key":  key,
        "prev": _mask(key, old_value),
        "new":  _mask(key, body.value),
    })
    await db.commit()
    return {"key": key, "value": body.value, "updated": True}


@router.post("/env/reload")
async def reload_env(
    db:    AsyncSession = Depends(get_db),
    admin: User         = Depends(require_role("admin")),
):
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)

    import importlib
    import config as cfg
    importlib.reload(cfg)

    await _audit(db, admin, "env.reloaded", detail={"path": str(ENV_PATH)})
    await db.commit()
    return {"reloaded": True, "path": str(ENV_PATH)}
