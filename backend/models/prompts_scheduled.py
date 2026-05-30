from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from core.db import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:     Mapped[int]        = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name:        Mapped[str]        = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content:     Mapped[str]        = mapped_column(Text, nullable=False)
    is_shared:   Mapped[bool]       = mapped_column(Boolean, default=False, nullable=False)
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScheduledPrompt(Base):
    __tablename__ = "scheduled_prompts"
    id:             Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:        Mapped[int]            = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name:           Mapped[str]            = mapped_column(String(100), nullable=False)
    prompt:         Mapped[str]            = mapped_column(Text, nullable=False)
    cron_expr:      Mapped[str]            = mapped_column(String(100), nullable=False)
    model_override: Mapped[str | None]     = mapped_column(String(100), nullable=True)
    workspace_id:   Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active:      Mapped[bool]           = mapped_column(Boolean, default=True, nullable=False)
    last_run_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:     Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScheduledPromptRun(Base):
    __tablename__ = "scheduled_prompt_runs"
    id:                  Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheduled_prompt_id: Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("scheduled_prompts.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at:          Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at:        Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status:              Mapped[str]            = mapped_column(String(20), nullable=False, default="running")
    output_file_id:      Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    error:               Mapped[str | None]     = mapped_column(Text, nullable=True)
