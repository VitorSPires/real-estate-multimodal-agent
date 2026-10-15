from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="real-estate-multimodal-agent", lifespan=lifespan)

# Every route lives under /api; the Vite dev server proxies /api to this app.
app.include_router(health.router, prefix="/api")
