import uuid
from datetime import datetime, timezone

from sqlalchemy import exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import SessionFactory
from .events import BookingEvent, RestaurantEvent, UserEvent
from .models import InboxMessage, Notification, RestaurantReplica, UserReplica
from .rules import REMINDER_CANCEL_TOPICS, plan_notifications


class PoisonMessage(Exception):...


async def handle_message(source: str, message_id: str, routing_key: str, data: dict) -> None:
    async with SessionFactory() as s:
        res = await s.execute(insert(InboxMessage).values(source=source, message_id=message_id)
                              .on_conflict_do_nothing().returning(InboxMessage.message_id))
        if res.first() is None:
            return
        try:
            if source == "identity.events":
                await _apply_user(s, UserEvent.model_validate(data))
            elif source == "catalog.events":
                await _apply_restaurant(s, RestaurantEvent.model_validate(data))
            elif source == "booking.events":
                await _apply_booking(s, routing_key, BookingEvent.model_validate(data))
        except ValueError as e:
            await s.rollback()
            raise PoisonMessage(str(e)) from e
        await s.commit()


async def _apply_user(s: AsyncSession, ev: UserEvent) -> None:
    stmt = insert(UserReplica).values(user_id=ev.user_id, email=ev.email, full_name=ev.full_name,
                                      phone=ev.phone, is_active=ev.is_active, version=ev.version)
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserReplica.user_id],
        set_={"email": stmt.excluded.email, "full_name": stmt.excluded.full_name, "phone": stmt.excluded.phone,
              "is_active": stmt.excluded.is_active, "version": stmt.excluded.version},
        where=UserReplica.version < stmt.excluded.version)
    await s.execute(stmt)


async def _apply_restaurant(s: AsyncSession, ev: RestaurantEvent) -> None:
    stmt = insert(RestaurantReplica).values(restaurant_id=ev.restaurant_id, name=ev.name,
                                            timezone=ev.timezone, version=ev.version)
    stmt = stmt.on_conflict_do_update(
        index_elements=[RestaurantReplica.restaurant_id],
        set_={"name": stmt.excluded.name, "timezone": stmt.excluded.timezone, "version": stmt.excluded.version},
        where=RestaurantReplica.version < stmt.excluded.version)
    await s.execute(stmt)


async def _apply_booking(s: AsyncSession, topic: str, ev: BookingEvent) -> None:
    if topic in REMINDER_CANCEL_TOPICS:
        await s.execute(update(Notification).where(
            Notification.booking_id == ev.booking_id, Notification.kind == "booking_reminder",
            Notification.status == "PENDING").values(status="CANCELLED"))

    plans = plan_notifications(topic, ev, datetime.now(timezone.utc),
                               settings.reminder_hours_before, settings.sms_enabled)

    if topic == "booking.cancelled":
        confirmed = await s.scalar(select(exists().where(
            Notification.booking_id == ev.booking_id, Notification.kind == "booking_confirmed")))
        if not confirmed:
            plans = []

    for p in plans:
        await s.execute(insert(Notification).values(
            id=uuid.uuid4(), user_id=ev.guest_id, booking_id=ev.booking_id, kind=p.kind, channel=p.channel,
            status="PENDING", attempts=0, next_attempt_at=p.send_after,
            event_data={"restaurant_id": str(ev.restaurant_id), "starts_at": ev.starts_at.isoformat(),
                        "party_size": ev.party_size},
            dedup_key=f"{ev.booking_id}:{p.kind}:{p.channel}",
        ).on_conflict_do_nothing(index_elements=["dedup_key"]))
