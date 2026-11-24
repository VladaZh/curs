import logging
from typing import Protocol

import redis.asyncio as redis

log = logging.getLogger("catalog.cache")


class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...
    async def delete(self, *keys: str) -> None: ...
    async def close(self) -> None: ...


class NullCache:
    async def get(self, key):
        return None

    async def set(self, key, value, ttl): ...
    async def delete(self, *keys): ...
    async def close(self): ...


class RedisCache:
    def __init__(self, url: str):
        self._r = redis.from_url(url, decode_responses=True)

    async def get(self, key):
        try:
            return await self._r.get(key)
        except Exception:
            log.warning("cache get failed", exc_info=True)
            return None

    async def set(self, key, value, ttl):
        try:
            await self._r.set(key, value, ex=ttl)
        except Exception:
            log.warning("cache set failed", exc_info=True)

    async def delete(self, *keys):
        try:
            if keys:
                await self._r.delete(*keys)
        except Exception:
            log.warning("cache delete failed", exc_info=True)

    async def close(self):
        await self._r.aclose()
