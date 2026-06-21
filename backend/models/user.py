from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    webhook_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True, index=True)
    has_onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    fact_saliences:       Mapped[dict]           = mapped_column(JSONB,  nullable=False, default=dict)
    last_used_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_summarized_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_scratchpad:      Mapped[dict | None]    = mapped_column(JSONB, nullable=True, default=dict)


class MemoryConflict(Base):
    __tablename__ = "memory_conflicts"
    id:            Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:       Mapped[int]            = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_a:        Mapped[str]            = mapped_column(Text, nullable=False)
    fact_b:        Mapped[str]            = mapped_column(Text, nullable=False)
    conflict_type: Mapped[str]            = mapped_column(String(32), nullable=False)
    resolution:    Mapped[str | None]     = mapped_column(String(32), nullable=True, default="unresolved")
    resolved_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:    Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserMemoryVersion(Base):
    __tablename__ = "user_memory_versions"
    id:              Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:         Mapped[int]        = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version:         Mapped[int]        = mapped_column(Integer, nullable=False)
    content:         Mapped[str]        = mapped_column(Text, nullable=False, default="")
    project_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:      Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserBehaviorProfile(Base):
    __tablename__ = "user_behavior_profiles"
    user_id:    Mapped[int]   = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    profile:    Mapped[dict]  = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserGoal(Base):
    __tablename__ = "user_goals"
    id:                       Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:                  Mapped[int]        = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title:                    Mapped[str]        = mapped_column(String(200), nullable=False)
    description:              Mapped[str  | None] = mapped_column(Text, nullable=True)
    status:                   Mapped[str]        = mapped_column(String(20), nullable=False, default="active")
    linked_conversation_ids:  Mapped[list]       = mapped_column(JSONB, nullable=False, default=list)
    created_at:               Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:               Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id:           Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:      Mapped[int]            = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type:   Mapped[str]            = mapped_column(String(64), nullable=False)
    payload:      Mapped[dict]           = mapped_column(JSONB, nullable=False)
    status:       Mapped[str]            = mapped_column(String(16), nullable=False, default="pending")
    error:        Mapped[str | None]     = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
