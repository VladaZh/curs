import asyncio
import hashlib
import json
import logging

import aio_pika

from .config import settings
from .handlers import PoisonMessage, handle_message

log = logging.getLogger("notification.consumer")

BINDINGS = {"identity.events": "user.*", "booking.events": "booking.*", "catalog.events": "restaurant.*"}
QUEUE, DLX, DLQ = "notification.events", "notification.dlx", "notification.dead"


async def _process(msg: aio_pika.abc.AbstractIncomingMessage) -> None:
    try:
        data = json.loads(msg.body)
    except ValueError as e:
        raise PoisonMessage("битый JSON") from e
    message_id = msg.message_id or hashlib.sha256(msg.body).hexdigest()[:32]
    await handle_message(msg.exchange, message_id, msg.routing_key or "", data)


async def consume() -> None:
    conn = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with conn:
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=20)

        dlx = await ch.declare_exchange(DLX, aio_pika.ExchangeType.FANOUT, durable=True)
        dlq = await ch.declare_queue(DLQ, durable=True)
        await dlq.bind(dlx)

        queue = await ch.declare_queue(QUEUE, durable=True, arguments={"x-dead-letter-exchange": DLX})
        for exchange, pattern in BINDINGS.items():
            ex = await ch.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC, durable=True)
            await queue.bind(ex, routing_key=pattern)

        async with queue.iterator() as it:
            async for msg in it:
                try:
                    await _process(msg)
                    await msg.ack()
                except PoisonMessage:
                    log.exception("poison message -> DLQ (%s %s)", msg.exchange, msg.routing_key)
                    await msg.reject(requeue=False)
                except Exception:
                    log.exception("handler failed, requeue")
                    await asyncio.sleep(2)
                    await msg.nack(requeue=True)


async def consumer_loop() -> None:
    while True:
        try:
            await consume()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("consumer crashed, restarting")
            await asyncio.sleep(5)
