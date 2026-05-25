from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    String,
    Integer,
    Text,
    ForeignKey,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid
from config import EMBEDDING_DIM
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

    cost_limit_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
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

class UserMemory(Base):
    __tablename__ = "user_memory"

    user_id:              Mapped[int]            = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    content:              Mapped[str]            = mapped_column(Text, nullable=False, default="")
    project_summary:      Mapped[str | None]     = mapped_column(Text, nullable=True)
    version:              Mapped[int]            = mapped_column(Integer, nullable=False, default=0)
    updated_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_summarized_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int]  = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str]    = mapped_column(String(100), nullable=False)
    history_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_enabled: Mapped[bool]        = mapped_column(Boolean,      nullable=False, default=True, server_default="true")
    system_prompt:  Mapped[str | None]  = mapped_column(Text,         nullable=True)
    locked_model:   Mapped[str | None]  = mapped_column(String(100),  nullable=True)
    created_at:     Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:     Mapped[datetime]    = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID]             = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str]    = mapped_column(String(20),  nullable=False)
    content: Mapped[str] = mapped_column(Text,        nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_tokens:     Mapped[int | None]   = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None]   = mapped_column(Integer, nullable=True)
    total_tokens:      Mapped[int | None]   = mapped_column(Integer, nullable=True)
    cost_usd:          Mapped[float | None] = mapped_column(Float,   nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MessageEmbedding(Base):
    __tablename__ = "message_embeddings"

    id:              Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id",      ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    content_snippet: Mapped[str]       = mapped_column(Text, nullable=False)
    embedding:       Mapped[list]      = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at:      Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserMemoryVersion(Base):
    __tablename__ = "user_memory_versions"

    id:              Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:         Mapped[int]        = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version:         Mapped[int]        = mapped_column(Integer, nullable=False)
    content:         Mapped[str]        = mapped_column(Text, nullable=False, default="")
    project_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:      Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConversationFile(Base):
    __tablename__ = "conversation_files"

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    file_id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id",          ondelete="CASCADE"), primary_key=True)
    attached_at:     Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FileVersion(Base):
    __tablename__ = "file_versions"

    id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    version:    Mapped[int]       = mapped_column(Integer, nullable=False)
    content:    Mapped[str]       = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id:              Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:         Mapped[int]            = mapped_column(ForeignKey("users.id",         ondelete="CASCADE"),   nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID|None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_name:       Mapped[str]            = mapped_column(String(64),  nullable=False)
    args:            Mapped[dict|None]      = mapped_column(JSONB,       nullable=True)
    result_preview:  Mapped[str|None]       = mapped_column(Text,        nullable=True)
    created_at:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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

    embedding: Mapped[list] = mapped_column(
        Vector(EMBEDDING_DIM),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

