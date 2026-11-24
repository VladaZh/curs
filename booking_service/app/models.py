import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, ExcludeConstraint, Range
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class TableReplica(Base):
    __tablename__ = "tables_replica"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(index=True)
    table_id: Mapped[uuid.UUID] = mapped_column()
    guest_id: Mapped[uuid.UUID] = mapped_column(index=True)
    party_size: Mapped[int] = mapped_column(Integer)
    period: Mapped[Range[datetime]] = mapped_column(TSTZRANGE)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        ExcludeConstraint(
            ("table_id", "="),
            ("period", "&&"),
            where=text("status IN ('PENDING','CONFIRMED','SEATED')"),
            using="gist",
            name="no_overlapping_bookings",
        ),
        UniqueConstraint("guest_id", "idempotency_key", name="uq_guest_idempotency"),
        CheckConstraint("party_size > 0", name="ck_party_size_positive"),
        Index(
            "ix_bookings_pending_expires",
            "expires_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_outbox_unpublished", "id", postgresql_where=text("published_at IS NULL")
        ),
    )
