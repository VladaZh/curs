"""Демо-данные для разработки: рестораны Roma и Firenze со столами и часами работы.

Включается переменной CATALOG_SEED_DEMO=true. Работает через обычный CatalogService, поэтому проходят
те же проверки, а события table.changed и restaurant.changed попадают в outbox и доезжают до Booking и Notification.
Идемпотентно: если в каталоге уже есть рестораны, ничего не делает.

Запускается только один раз при создании ресторанов в базе. Либо администратор БД может сам создать рестораны
"""

import logging
import uuid

from sqlalchemy import func, select

from .auth import CurrentUser
from .cache import Cache
from .db import SessionFactory
from .models import Restaurant
from .schemas import RestaurantCreate, TableCreate
from .service import CatalogService

log = logging.getLogger("catalog.seed")

SYSTEM_ADMIN = CurrentUser(id=uuid.UUID(int=0), role="admin", restaurant_id=None)

HOURS = [{"weekday": day, "opens": "12:00", "closes": "23:00"} for day in range(7)]
RESTAURANTS = [
    {
        "name": "Roma",
        "address": "ул. Покровка, 24",
        "city": "Москва",
        "timezone": "Europe/Moscow",
    },
    {
        "name": "Firenze",
        "address": "ул. Остоженка, 23",
        "city": "Москва",
        "timezone": "Europe/Moscow",
    },
]
TABLES = [
    ("T1", 2),
    ("T2", 2),
    ("T3", 2),
    ("T4", 4),
    ("T5", 4),
    ("T6", 4),
    ("T7", 6),
    ("T8", 8),
]


async def seed_demo(cache: Cache) -> None:
    async with SessionFactory() as session:
        if await session.scalar(select(func.count()).select_from(Restaurant)):
            log.info("seed: в каталоге уже есть рестораны, пропускаем")
            return

        svc = CatalogService(session, cache)
        for spec in RESTAURANTS:
            restaurant = await svc.create_restaurant(
                SYSTEM_ADMIN, RestaurantCreate(**spec, hours=HOURS)
            )
            for label, capacity in TABLES:
                await svc.add_table(
                    SYSTEM_ADMIN,
                    restaurant.id,
                    TableCreate(label=label, capacity=capacity),
                )
            log.info(
                "seed: создан ресторан %s (%d столов)", restaurant.name, len(TABLES)
            )
