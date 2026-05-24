from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL

# ─────────────────────────────────────────────
# SINGLE SOURCE OF TRUTH BASE
# ─────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────

async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ─────────────────────────────────────────────
# SESSION DEPENDENCY
# ─────────────────────────────────────────────

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# ─────────────────────────────────────────────
# INIT DB (CRITICAL FIX HERE)
# ─────────────────────────────────────────────

async def init_db() -> None:
    async with async_engine.begin() as conn:
        # THIS is what actually creates tables
        await conn.run_sync(Base.metadata.create_all)