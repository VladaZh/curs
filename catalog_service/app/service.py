import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import CurrentUser
from .cache import Cache
from .config import settings
from .errors import Conflict, Forbidden, NotFound
from .models import DiningTable, OpeningHours, OutboxEvent, Restaurant
from .schemas import (
    HoursIn,
    RestaurantCreate,
    RestaurantOut,
    RestaurantPatch,
    TableCreate,
    TableOut,
    TablePatch,
)

_RESTAURANT = TypeAdapter(RestaurantOut)
_RESTAURANTS = TypeAdapter(list[RestaurantOut])
_TABLES = TypeAdapter(list[TableOut])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CatalogService:
    def __init__(self, session: AsyncSession, cache: Cache):
        self.s, self.cache = session, cache

    async def list_restaurants(self, city: str | None) -> list[RestaurantOut]:
        async def load():
            q = select(Restaurant).where(Restaurant.is_active).order_by(Restaurant.name)
            if city:
                q = q.where(func.lower(Restaurant.city) == city.lower())
            return [
                RestaurantOut.model_validate(r) for r in (await self.s.scalars(q)).all()
            ]

        return await self._cached(
            f"restaurants:{(city or 'all').lower()}",
            settings.list_cache_ttl_seconds,
            _RESTAURANTS,
            load,
        )

    async def get_restaurant(self, restaurant_id: uuid.UUID) -> RestaurantOut:
        async def load():
            r = await self.s.get(Restaurant, restaurant_id)
            if r is None:
                raise NotFound("Ресторан не найден")
            return RestaurantOut.model_validate(r)

        return await self._cached(
            f"restaurant:{restaurant_id}", settings.cache_ttl_seconds, _RESTAURANT, load
        )

    async def list_tables(self, restaurant_id: uuid.UUID) -> list[TableOut]:
        async def load():
            q = (
                select(DiningTable)
                .where(DiningTable.restaurant_id == restaurant_id)
                .order_by(DiningTable.label)
            )
            return [TableOut.model_validate(t) for t in (await self.s.scalars(q)).all()]

        return await self._cached(
            f"tables:{restaurant_id}", settings.cache_ttl_seconds, _TABLES, load
        )

    async def create_restaurant(
        self, user: CurrentUser, data: RestaurantCreate
    ) -> RestaurantOut:
        self._require_admin(user)
        r = Restaurant(**data.model_dump(exclude={"hours"}))
        r.hours = [OpeningHours(**h.model_dump()) for h in data.hours]
        self.s.add(r)
        await self.s.flush()
        self._emit_restaurant(r)
        await self.s.commit()
        await self._invalidate(r.id, r.city)
        return RestaurantOut.model_validate(r)

    async def update_restaurant(
        self, user: CurrentUser, rid: uuid.UUID, patch: RestaurantPatch
    ) -> RestaurantOut:
        self._require_admin(user)
        r = await self._lock_restaurant(rid)
        old_city = r.city
        for k, v in patch.model_dump(exclude_unset=True).items():
            setattr(r, k, v)
        r.version += 1
        self._emit_restaurant(r)
        await self.s.commit()
        await self._invalidate(rid, old_city, r.city)
        return RestaurantOut.model_validate(r)

    async def replace_hours(
        self, user: CurrentUser, rid: uuid.UUID, hours: list[HoursIn]
    ) -> RestaurantOut:
        self._authorize(user, rid)
        r = await self._lock_restaurant(rid)
        r.hours.clear()
        await self.s.flush()
        r.hours.extend(OpeningHours(**h.model_dump()) for h in hours)
        r.version += 1
        await self.s.flush()
        self._emit_restaurant(r)
        await self.s.commit()
        await self._invalidate(rid, r.city)
        return RestaurantOut.model_validate(r)

    async def add_table(
        self, user: CurrentUser, rid: uuid.UUID, data: TableCreate
    ) -> TableOut:
        self._authorize(user, rid)
        r = await self.s.get(Restaurant, rid)
        if r is None:
            raise NotFound("Ресторан не найден")
        t = DiningTable(restaurant_id=rid, **data.model_dump())
        self.s.add(t)
        try:
            await self.s.flush()
        except IntegrityError:
            await self.s.rollback()
            raise Conflict("Стол с такой меткой уже есть в этом ресторане")
        self._emit_table(t)
        await self.s.commit()
        await self._invalidate(rid, r.city)
        return TableOut.model_validate(t)

    async def update_table(
        self, user: CurrentUser, rid: uuid.UUID, table_id: uuid.UUID, patch: TablePatch
    ) -> TableOut:
        self._authorize(user, rid)
        t = await self.s.scalar(
            select(DiningTable)
            .where(DiningTable.id == table_id, DiningTable.restaurant_id == rid)
            .with_for_update()
        )
        if t is None:
            raise NotFound("Стол не найден")
        for k, v in patch.model_dump(exclude_unset=True).items():
            setattr(t, k, v)
        t.version += 1
        self._emit_table(t)
        await self.s.commit()
        await self.cache.delete(f"tables:{rid}")
        return TableOut.model_validate(t)

    async def resync(self, user: CurrentUser) -> int:
        """Переиздаёт текущее состояние всех сущностей. Реплики с актуальной версией его проигнорируют,
        а новые или отставшие догонят каталог."""
        self._require_admin(user)
        n = 0
        for r in (await self.s.scalars(select(Restaurant))).all():
            self._emit_restaurant(r)
            n += 1
        for t in (await self.s.scalars(select(DiningTable))).all():
            self._emit_table(t)
            n += 1
        await self.s.commit()
        return n

    async def _cached(
        self, key: str, ttl: int, adapter: TypeAdapter, loader: Callable[[], Awaitable]
    ):
        raw = await self.cache.get(key)
        if raw:
            return adapter.validate_json(raw)
        value = await loader()
        await self.cache.set(key, adapter.dump_json(value).decode(), ttl)
        return value

    async def _invalidate(self, rid: uuid.UUID, *cities: str) -> None:
        keys = [f"restaurant:{rid}", f"tables:{rid}", "restaurants:all"]
        keys += [f"restaurants:{c.lower()}" for c in cities]
        await self.cache.delete(*keys)

    async def _lock_restaurant(self, rid: uuid.UUID) -> Restaurant:
        r = await self.s.scalar(
            select(Restaurant).where(Restaurant.id == rid).with_for_update()
        )
        if r is None:
            raise NotFound("Ресторан не найден")
        return r

    @staticmethod
    def _require_admin(user: CurrentUser) -> None:
        if user.role != "admin":
            raise Forbidden("Только для администратора сети")

    @staticmethod
    def _authorize(user: CurrentUser, rid: uuid.UUID) -> None:
        if user.role == "admin" or (user.role == "staff" and user.restaurant_id == rid):
            return
        raise Forbidden("Нет доступа к этому ресторану")

    def _emit_restaurant(self, r: Restaurant) -> None:
        self.s.add(
            OutboxEvent(
                topic="restaurant.changed",
                payload={
                    "restaurant_id": str(r.id),
                    "name": r.name,
                    "timezone": r.timezone,
                    "slot_minutes": r.slot_minutes,
                    "booking_horizon_days": r.booking_horizon_days,
                    "is_active": r.is_active,
                    "version": r.version,
                    "hours": [
                        {
                            "weekday": h.weekday,
                            "opens": h.opens.strftime("%H:%M"),
                            "closes": h.closes.strftime("%H:%M"),
                        }
                        for h in r.hours
                    ],
                    "occurred_at": _now_iso(),
                },
            )
        )

    def _emit_table(self, t: DiningTable) -> None:
        self.s.add(
            OutboxEvent(
                topic="table.changed",
                payload={
                    "table_id": str(t.id),
                    "restaurant_id": str(t.restaurant_id),
                    "capacity": t.capacity,
                    "is_active": t.is_active,
                    "version": t.version,
                    "occurred_at": _now_iso(),
                },
            )
        )
