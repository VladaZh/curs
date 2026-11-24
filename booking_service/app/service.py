import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.config import settings
from app.domain import (
    ACTIVE_STATUSES,
    BestFitStrategy,
    BookingStatus as S,
    Forbidden,
    HoldExpired,
    NoAvailability,
    NotFound,
    TableSelectionStrategy,
    ensure_transition,
)
from app.models import Booking, OutboxEvent, TableReplica


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BookingService:
    def __init__(
        self, session: AsyncSession, strategy: TableSelectionStrategy | None = None
    ):
        self.s = session
        self.strategy = strategy or BestFitStrategy()

    async def free_tables(
        self, restaurant_id: uuid.UUID, period: Range, party_size: int
    ):
        busy = exists().where(
            Booking.table_id == TableReplica.id,
            Booking.status.in_([x.value for x in ACTIVE_STATUSES]),
            Booking.period.overlaps(period),
        )
        q = select(TableReplica).where(
            TableReplica.restaurant_id == restaurant_id,
            TableReplica.is_active,
            TableReplica.capacity >= party_size,
            ~busy,
        )
        return list((await self.s.scalars(q)).all())

    def period_for(self, starts_at: datetime) -> Range:
        return Range(
            starts_at, starts_at + timedelta(minutes=settings.slot_minutes), bounds="[)"
        )

    async def create_hold(
        self, user: CurrentUser, restaurant_id, starts_at, party_size, idem_key
    ):
        if idem_key:
            existing = await self.s.scalar(
                select(Booking).where(
                    Booking.guest_id == user.id, Booking.idempotency_key == idem_key
                )
            )
            if existing:
                return existing

        await self.expire_stale()
        period = self.period_for(starts_at)
        candidates = self.strategy.order(
            await self.free_tables(restaurant_id, period, party_size), party_size
        )

        for table in candidates:
            booking = Booking(
                restaurant_id=restaurant_id,
                table_id=table.id,
                guest_id=user.id,
                party_size=party_size,
                period=period,
                status=S.PENDING.value,
                expires_at=_now() + timedelta(minutes=settings.hold_ttl_minutes),
                idempotency_key=idem_key,
            )
            try:
                async with self.s.begin_nested():
                    self.s.add(booking)
                    await self.s.flush()
            except IntegrityError as e:
                if "no_overlapping_bookings" in str(e.orig):
                    continue
                raise
            self._emit(booking)
            await self.s.commit()
            return booking
        raise NoAvailability("На это время нет свободных столов")

    async def confirm(self, user: CurrentUser, booking_id: uuid.UUID):
        b = await self._get_for_update(user, booking_id)
        if b.status == S.PENDING.value and b.expires_at and b.expires_at < _now():
            await self._transition(b, S.EXPIRED)
            await self.s.commit()
            raise HoldExpired("Время удержания слота истекло")
        await self._transition(b, S.CONFIRMED)
        await self.s.commit()
        return b

    async def cancel(self, user: CurrentUser, booking_id: uuid.UUID):
        b = await self._get_for_update(user, booking_id)
        await self._transition(b, S.CANCELLED)
        await self.s.commit()
        return b

    async def staff_set_status(self, user: CurrentUser, booking_id: uuid.UUID, new: S):
        if user.role not in ("staff", "admin"):
            raise Forbidden("Только для сотрудников")
        if new in (S.PENDING, S.CONFIRMED, S.EXPIRED):
            raise Forbidden("Этот статус сотрудник выставлять не может")
        b = await self._get_for_update(user, booking_id)
        await self._transition(b, new)
        await self.s.commit()
        return b

    async def get(self, user: CurrentUser, booking_id: uuid.UUID):
        b = await self.s.get(Booking, booking_id)
        self._check_access(user, b)
        return b

    async def list_mine(self, user: CurrentUser):
        q = (
            select(Booking)
            .where(Booking.guest_id == user.id)
            .order_by(Booking.created_at.desc())
        )
        return list((await self.s.scalars(q)).all())

    async def list_for_restaurant(
        self, user: CurrentUser, restaurant_id: uuid.UUID, day: datetime
    ):
        if user.role == "guest" or (
            user.role == "staff" and user.restaurant_id != restaurant_id
        ):
            raise Forbidden("Нет доступа к этому ресторану")
        day_range = Range(day, day + timedelta(days=1), bounds="[)")
        q = (
            select(Booking)
            .where(
                Booking.restaurant_id == restaurant_id,
                Booking.period.overlaps(day_range),
            )
            .order_by(Booking.period)
        )
        return list((await self.s.scalars(q)).all())

    async def expire_stale(self) -> int:
        q = (
            select(Booking)
            .where(Booking.status == S.PENDING.value, Booking.expires_at < _now())
            .with_for_update(skip_locked=True)
        )
        rows = (await self.s.scalars(q)).all()
        for b in rows:
            await self._transition(b, S.EXPIRED)
        if rows:
            await self.s.commit()
        return len(rows)

    async def _get_for_update(self, user, booking_id):
        b = await self.s.scalar(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        self._check_access(user, b)
        return b

    @staticmethod
    def _check_access(user: CurrentUser, b: Booking | None):
        if b is None:
            raise NotFound("Бронь не найдена")
        ok = (
            user.role == "admin"
            or (user.role == "staff" and user.restaurant_id == b.restaurant_id)
            or b.guest_id == user.id
        )
        if not ok:
            raise NotFound("Бронь не найдена")

    async def _transition(self, b: Booking, new: S):
        ensure_transition(S(b.status), new)
        b.status = new.value
        if new != S.PENDING:
            b.expires_at = None
        self._emit(b)

    def _emit(self, b: Booking):
        status = S(b.status)
        name = "created" if status == S.PENDING else status.value.lower()
        self.s.add(
            OutboxEvent(
                topic=f"booking.{name}",
                payload={
                    "booking_id": str(b.id),
                    "restaurant_id": str(b.restaurant_id),
                    "table_id": str(b.table_id),
                    "guest_id": str(b.guest_id),
                    "party_size": b.party_size,
                    "status": b.status,
                    "starts_at": b.period.lower.isoformat(),
                    "ends_at": b.period.upper.isoformat(),
                    "occurred_at": _now().isoformat(),
                },
            )
        )
