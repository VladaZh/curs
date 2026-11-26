import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import router
from .channels import build_channels
from .config import settings
from .consumer import consumer_loop
from .dispatcher import dispatcher_loop
from .errors import DomainError

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(dispatcher_loop(build_channels(settings)))]
    if settings.rabbitmq_url:
        tasks.append(asyncio.create_task(consumer_loop()))
    yield
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Notification Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.http_status, content={"detail": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok"}
