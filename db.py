"""
db.py
─────
Async SQLAlchemy engine + session dependency.

Provides:
- async_engine     → shared engine instance
- AsyncSessionLocal → session factory
- get_db()         → FastAPI dependency (yields a session per request)
- init_db()        → creates all tables (called at startup)
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL

# ── Engine ────────────────────────────────────────────────────────────────────
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,        # set True locally to see SQL in logs
    pool_pre_ping=True,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Base class for all models ─────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass

# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# ── Table creation (called once at startup) ───────────────────────────────────
async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)