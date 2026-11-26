import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Protocol

import aio_pika
from sqlalchemy import select

from .db import SessionFactory
from .models import OutboxEvent

log = logging.getLogger("identity.messaging")
EXCHANGE = "identity.events"


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
                EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
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
