from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from core.db import Base


class Invitation(Base):
    __tablename__ = "invitations"
    id:            Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token:         Mapped[str]            = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_by_id: Mapped[int]            = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email:         Mapped[str | None]     = mapped_column(String(254), nullable=True)
    used_by_id:    Mapped[int | None]     = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at:    Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
