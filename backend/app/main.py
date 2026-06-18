"""FastAPI gateway entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health, tasks
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import get_logger, setup_logging
from app.core.observability import init_telemetry

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_telemetry("ai-stt-api")
    log.info("api.startup", env=settings.app_env, version=__version__)
    yield
    log.info("api.shutdown")


app = FastAPI(
    title="AI Processing Platform",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_prod else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_dev else [],  # tightened per env at deploy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)
app.include_router(health.router)
app.include_router(tasks.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "ai-stt-api", "version": __version__}
