from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
from core.db import Base


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"
    id:              Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id:         Mapped[int]            = mapped_column(ForeignKey("users.id",         ondelete="CASCADE"),   nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID|None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_name:       Mapped[str]            = mapped_column(String(64),  nullable=False)
    args:            Mapped[dict|None]      = mapped_column(JSONB,       nullable=True)
    result_preview:  Mapped[str|None]       = mapped_column(Text,        nullable=True)
    created_at:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
