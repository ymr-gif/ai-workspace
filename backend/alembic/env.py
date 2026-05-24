import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# -------------------------------------------------------
# Ensure project root is importable
# -------------------------------------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# -------------------------------------------------------
# Import ORM metadata (CRITICAL)
# -------------------------------------------------------
from core.db import Base
import models  # noqa: F401

# -------------------------------------------------------
# Alembic config
# -------------------------------------------------------
config = context.config

# -------------------------------------------------------
# Logging setup
# -------------------------------------------------------
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -------------------------------------------------------
# Database URL handling
# -------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment variables")

# Alembic MUST use sync driver (NOT asyncpg)
if "+asyncpg" in DATABASE_URL:
    ALEMBIC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")
else:
    ALEMBIC_DATABASE_URL = DATABASE_URL

# Force psycopg driver for migrations
if "postgresql://" in ALEMBIC_DATABASE_URL and "+psycopg" not in ALEMBIC_DATABASE_URL:
    ALEMBIC_DATABASE_URL = ALEMBIC_DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://"
    )

config.set_main_option("sqlalchemy.url", ALEMBIC_DATABASE_URL)

# -------------------------------------------------------
# Metadata for autogenerate
# -------------------------------------------------------
target_metadata = Base.metadata


# -------------------------------------------------------
# Offline migrations
# -------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# -------------------------------------------------------
# Online migrations
# -------------------------------------------------------
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# -------------------------------------------------------
# Entry point
# -------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()