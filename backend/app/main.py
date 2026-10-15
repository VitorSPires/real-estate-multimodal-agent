from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers the tables before init_db)
from app.api import chat, health, ingestions, listings, live
from app.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="real-estate-multimodal-agent", lifespan=lifespan)

# Every route lives under /api; the Vite dev server proxies /api to this app.
for module in (health, ingestions, listings, chat, live):
    app.include_router(module.router, prefix="/api")
