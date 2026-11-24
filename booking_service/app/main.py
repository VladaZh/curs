import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import router
from app.config import settings
from app.domain import DomainError
from app.messaging import (
    LogPublisher,
    RabbitPublisher,
    consume_catalog_events,
    expiry_loop,
    relay_loop,
)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    publisher = (
        RabbitPublisher(settings.rabbitmq_url)
        if settings.rabbitmq_url
        else LogPublisher()
    )
    tasks = [
        asyncio.create_task(relay_loop(publisher, stop)),
        asyncio.create_task(expiry_loop(stop)),
    ]
    if settings.rabbitmq_url:
        tasks.append(asyncio.create_task(consume_catalog_events(stop)))
    yield
    stop.set()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await publisher.close()


app = FastAPI(title="Booking Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.http_status, content={"detail": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok"}
