import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import router
from .config import settings
from .db import SessionFactory
from .errors import DomainError
from .messaging import LogPublisher, RabbitPublisher, relay_loop
from .service import IdentityService

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
        async with SessionFactory() as s:
            await IdentityService(s).ensure_admin(settings.bootstrap_admin_email,
                                                  settings.bootstrap_admin_password)
    publisher = RabbitPublisher(settings.rabbitmq_url) if settings.rabbitmq_url else LogPublisher()
    stop = asyncio.Event()
    relay = asyncio.create_task(relay_loop(publisher, stop))
    yield
    stop.set()
    relay.cancel()
    await asyncio.gather(relay, return_exceptions=True)
    await publisher.close()


app = FastAPI(title="Identity Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    headers = {"WWW-Authenticate": "Bearer"} if exc.http_status == 401 else None
    return JSONResponse(status_code=exc.http_status, content={"detail": str(exc)}, headers=headers)


@app.get("/health")
async def health():
    return {"status": "ok"}
