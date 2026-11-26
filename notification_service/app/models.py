import uuid
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class InboxMessage(Base):
    __tablename__ = "inbox"

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class UserReplica(Base):
    __tablename__ = "users_replica"

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class RestaurantReplica(Base):
    __tablename__ = "restaurants_replica"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=0)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_data: Mapped[dict] = mapped_column(JSONB)
    dedup_key: Mapped[str] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_notification_dedup"),
        Index("ix_notifications_due", "next_attempt_at", postgresql_where=text("status IN ('PENDING','SENDING')")),
    )
