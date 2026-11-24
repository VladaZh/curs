import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import router
from .cache import NullCache, RedisCache
from .config import settings
from .errors import DomainError
from .messaging import LogPublisher, RabbitPublisher, relay_loop

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cache = (
        RedisCache(settings.redis_url) if settings.redis_url else NullCache()
    )
    publisher = (
        RabbitPublisher(settings.rabbitmq_url)
        if settings.rabbitmq_url
        else LogPublisher()
    )
    stop = asyncio.Event()
    relay = asyncio.create_task(relay_loop(publisher, stop))
    yield
    stop.set()
    relay.cancel()
    await asyncio.gather(relay, return_exceptions=True)
    await publisher.close()
    await app.state.cache.close()


app = FastAPI(title="Catalog Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.http_status, content={"detail": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok"}
