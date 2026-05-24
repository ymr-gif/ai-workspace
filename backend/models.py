from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    Integer,
    Text,
    ForeignKey,
    func,
    Float
)

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime
import uuid
from core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password: Mapped[str] = mapped_column(
        String(256),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(32),
        default="user",
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    workspace_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True
    )

    filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False
    )

    mime_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    storage_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True
    )

    upload_status: Mapped[str] = mapped_column(
        String(32),
        default="uploaded",
        nullable=False,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

class FileChunk(Base):
    __tablename__ = "file_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("files.id"),
        nullable=False,
        index=True
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

