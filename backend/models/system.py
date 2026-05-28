from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from core.db import Base


class SystemConfig(Base):
    __tablename__ = "system_config"
    key:        Mapped[str]        = mapped_column(String(64), primary_key=True)
    value:      Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
