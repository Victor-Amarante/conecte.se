from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import shutdown_agent
from app.core.exceptions import (
    AppException,
    WebhookIgnoredError,
    app_exception_handler,
    webhook_ignored_handler,
)
from app.db.session import dispose_engine
from app.services.registry import close_all
from app.routers.bus_location import router as bus_location_router
from app.routers.transit import router as transit_router
from app.routers.webhook import router as webhook_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_all()
    await shutdown_agent()
    await dispose_engine()


app = FastAPI(title="Conectese", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(WebhookIgnoredError, webhook_ignored_handler)
app.add_exception_handler(AppException, app_exception_handler)

app.include_router(webhook_router)
app.include_router(bus_location_router)
app.include_router(transit_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
