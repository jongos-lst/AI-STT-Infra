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


def _auto_instrument(app: FastAPI) -> None:
    """Attach OTel auto-instrumentations. Each call is best-effort —
    missing libs in dev shouldn't keep the app from booting."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz")
    except Exception as e:
        log.warning("otel.fastapi.skipped", error=str(e))
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        from app.infra.db import engine as _engine
        SQLAlchemyInstrumentor().instrument(engine=_engine.sync_engine)
    except Exception as e:
        log.warning("otel.sqlalchemy.skipped", error=str(e))
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
    except Exception as e:
        log.warning("otel.redis.skipped", error=str(e))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_telemetry("ai-stt-api")
    _auto_instrument(_app)
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
