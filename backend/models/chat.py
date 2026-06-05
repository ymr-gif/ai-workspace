from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid
from config import EMBEDDING_DIM
from core.db import Base


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int]  = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str]    = mapped_column(String(100), nullable=False)
    history_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_enabled: Mapped[bool]        = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    system_prompt:  Mapped[str | None]  = mapped_column(Text, nullable=True)
    locked_model:   Mapped[str | None]  = mapped_column(String(100), nullable=True)
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
    token_estimate:    Mapped[bool | None]  = mapped_column(Boolean, nullable=True)
    # Ordered "behind the scenes" trace for this turn (pipeline stages, tools,
    # errors) — surfaced live + persisted for the collapsible Activity strip.
    activity_trace:    Mapped[list | None]  = mapped_column(JSONB,   nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MessageEmbedding(Base):
    __tablename__ = "message_embeddings"
    id:              Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id",      ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    content_snippet: Mapped[str]       = mapped_column(Text, nullable=False)
    embedding:       Mapped[list]      = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at:      Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ConversationFile(Base):
    __tablename__ = "conversation_files"
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    file_id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id",          ondelete="CASCADE"), primary_key=True)
    attached_at:     Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
