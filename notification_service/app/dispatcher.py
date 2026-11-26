import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_, select

from .channels import Channel, PermanentError
from .config import settings
from .db import SessionFactory
from .models import InboxMessage, Notification, RestaurantReplica, UserReplica
from .templates import render

log = logging.getLogger("notification.dispatcher")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def claim_batch(limit: int) -> list[uuid.UUID]:
    now = _now()
    async with SessionFactory() as s:
        q = (select(Notification).where(or_(
            and_(Notification.status == "PENDING", Notification.next_attempt_at <= now),
            and_(Notification.status == "SENDING", Notification.lease_until < now)))
            .order_by(Notification.next_attempt_at).limit(limit).with_for_update(skip_locked=True))
        rows = (await s.scalars(q)).all()
        for n in rows:
            n.status, n.lease_until = "SENDING", now + timedelta(seconds=settings.lease_seconds)
        await s.commit()
        return [n.id for n in rows]


async def _finish(nid: uuid.UUID, status: str, error: str | None = None, retry: bool = False) -> None:
    async with SessionFactory() as s:
        n = await s.scalar(select(Notification).where(Notification.id == nid).with_for_update())
        if n is None or n.status != "SENDING":
            return
        n.lease_until, n.last_error = None, error
        if retry:
            n.attempts += 1
            if n.attempts >= settings.max_attempts:
                n.status = "FAILED"
            else:
                delay = min(settings.retry_base_seconds * 2 ** n.attempts, settings.retry_cap_seconds)
                n.status = "PENDING"
                n.next_attempt_at = _now() + timedelta(seconds=delay * random.uniform(0.8, 1.2))
        else:
            n.status = status
            if status == "SENT":
                n.sent_at = _now()
        await s.commit()


async def deliver(nid: uuid.UUID, channels: dict[str, Channel]) -> None:
    async with SessionFactory() as s:
        n = await s.get(Notification, nid)
        if n is None or n.status != "SENDING":
            return
        user = await s.get(UserReplica, n.user_id)
        resto = await s.get(RestaurantReplica, uuid.UUID(n.event_data["restaurant_id"]))
        kind, channel, data = n.kind, n.channel, dict(n.event_data)

    try:
        if user is None or resto is None:
            raise RuntimeError("реплики пользователя или ресторана ещё не получены")
        address = user.email if channel == "email" else user.phone
        if not user.is_active or not address:
            return await _finish(nid, "SKIPPED", "нет адреса или пользователь отключён")
        msg = render(kind, channel, name=user.full_name, restaurant=resto.name, timezone=resto.timezone,
                     starts_at=datetime.fromisoformat(data["starts_at"]), party_size=data["party_size"])
        await channels[channel].send(address, msg, idempotency_key=str(nid))
        await _finish(nid, "SENT")
    except PermanentError as e:
        await _finish(nid, "FAILED", str(e)[:500])
    except Exception as e:
        log.warning("delivery failed for %s: %s", nid, e)
        await _finish(nid, "PENDING", str(e)[:500], retry=True)


async def cleanup_inbox() -> None:
    async with SessionFactory() as s:
        await s.execute(delete(InboxMessage).where(
            InboxMessage.received_at < _now() - timedelta(days=settings.inbox_retention_days)))
        await s.commit()


async def dispatcher_loop(channels: dict[str, Channel]) -> None:
    last_cleanup = 0.0
    while True:
        try:
            ids = await claim_batch(settings.dispatch_batch)
            await asyncio.gather(*(deliver(i, channels) for i in ids))
            if asyncio.get_running_loop().time() - last_cleanup > 3600:
                await cleanup_inbox()
                last_cleanup = asyncio.get_running_loop().time()
            if not ids:
                await asyncio.sleep(settings.dispatch_poll_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("dispatcher iteration failed")
            await asyncio.sleep(5)
