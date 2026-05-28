from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
from core.db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cost_limit_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserInsight(Base):
    __tablename__ = "user_insights"
    id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:    Mapped[int]       = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content:    Mapped[str]       = mapped_column(Text, nullable=False)
    is_read:    Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    id:             Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id:       Mapped[int]       = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action:         Mapped[str]       = mapped_column(String(64), nullable=False, index=True)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    detail:         Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at:     Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class UserMemory(Base):
    __tablename__ = "user_memory"
    user_id:              Mapped[int]            = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    content:              Mapped[str]            = mapped_column(Text, nullable=False, default="")
    project_summary:      Mapped[str | None]     = mapped_column(Text, nullable=True)
    version:              Mapped[int]            = mapped_column(Integer, nullable=False, default=0)
    salience:             Mapped[float]          = mapped_column(Float,   nullable=False, default=1.0)
    confidence:           Mapped[float]          = mapped_column(Float,   nullable=False, default=1.0)
    last_used_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_summarized_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserMemoryVersion(Base):
    __tablename__ = "user_memory_versions"
    id:              Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:         Mapped[int]        = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version:         Mapped[int]        = mapped_column(Integer, nullable=False)
    content:         Mapped[str]        = mapped_column(Text, nullable=False, default="")
    project_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:      Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
