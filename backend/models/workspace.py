from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from core.db import Base


class Workspace(Base):
    __tablename__ = "workspaces"
    id:            Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:       Mapped[int]        = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name:          Mapped[str]        = mapped_column(String(120), nullable=False)
    description:   Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:    Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:    Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WorkspaceMemory(Base):
    __tablename__ = "workspace_memory"
    id:              Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id:    Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    content:         Mapped[str | None]    = mapped_column(Text, nullable=True)
    project_summary: Mapped[str | None]    = mapped_column(Text, nullable=True)
    version:         Mapped[int]           = mapped_column(Integer, nullable=False, default=0)
    updated_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
