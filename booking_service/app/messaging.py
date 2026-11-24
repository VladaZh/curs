import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Protocol

import aio_pika
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionFactory
from app.models import OutboxEvent, TableReplica
from app.service import BookingService

log = logging.getLogger("booking.messaging")


class Publisher(Protocol):
    async def publish(self, topic: str, payload: dict, message_id: str) -> None: ...
    async def close(self) -> None: ...


class LogPublisher:
    async def publish(self, topic, payload, message_id):
        log.info("EVENT %s %s", topic, json.dumps(payload))

    async def close(self): ...


class RabbitPublisher:
    def __init__(self, url: str):
        self.url, self._conn, self._ex = url, None, None

    async def _ensure(self):
        if self._ex is None:
            self._conn = await aio_pika.connect_robust(self.url)
            ch = await self._conn.channel(publisher_confirms=True)
            self._ex = await ch.declare_exchange(
                "booking.events", aio_pika.ExchangeType.TOPIC, durable=True
            )

    async def publish(self, topic, payload, message_id):
        await self._ensure()
        await self._ex.publish(
            aio_pika.Message(
                json.dumps(payload).encode(),
                message_id=message_id,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=topic,
        )

    async def close(self):
        if self._conn:
            await self._conn.close()


async def relay_loop(publisher: Publisher, stop: asyncio.Event) -> None:
    """Забирает неотправленные события; at-least-once, консьюмеры дедуплицируют по message_id."""
    while not stop.is_set():
        sent = 0
        try:
            async with SessionFactory() as s:
                q = (
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.id)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
                for ev in (await s.scalars(q)).all():
                    await publisher.publish(ev.topic, ev.payload, str(ev.id))
                    ev.published_at = datetime.now(timezone.utc)
                    sent += 1
                await s.commit()
        except Exception:
            log.exception("outbox relay failed")
            await asyncio.sleep(5)
        if not sent:
            await asyncio.sleep(1)


async def expiry_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with SessionFactory() as s:
                await BookingService(s).expire_stale()
        except Exception:
            log.exception("expiry loop failed")
        await asyncio.sleep(30)


async def apply_table_event(data: dict) -> None:
    """Идемпотентный upsert: дубли и устаревшие версии игнорируются."""
    stmt = insert(TableReplica).values(
        id=data["table_id"],
        restaurant_id=data["restaurant_id"],
        capacity=data["capacity"],
        is_active=data.get("is_active", True),
        version=data["version"],
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[TableReplica.id],
        set_={
            "capacity": stmt.excluded.capacity,
            "is_active": stmt.excluded.is_active,
            "version": stmt.excluded.version,
            "restaurant_id": stmt.excluded.restaurant_id,
        },
        where=TableReplica.version < stmt.excluded.version,
    )
    async with SessionFactory() as s:
        await s.execute(stmt)
        await s.commit()


async def consume_catalog_events(stop: asyncio.Event) -> None:
    conn = await aio_pika.connect_robust(settings.rabbitmq_url)
    ch = await conn.channel()
    ex = await ch.declare_exchange(
        "catalog.events", aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await ch.declare_queue("booking.catalog", durable=True)
    await queue.bind(ex, routing_key="table.*")
    async with queue.iterator() as it:
        async for msg in it:
            async with msg.process(requeue=True):
                await apply_table_event(json.loads(msg.body))
