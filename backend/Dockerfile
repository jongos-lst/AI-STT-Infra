# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# uv for fast deps
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv

WORKDIR /app

# ---- deps layer ----
FROM base AS deps
COPY pyproject.toml ./
RUN uv pip install --system --no-deps -r <(uv pip compile pyproject.toml --quiet) \
 || uv pip install --system fastapi uvicorn[standard] pydantic pydantic-settings \
      sqlalchemy[asyncio] asyncpg alembic redis google-cloud-pubsub google-cloud-storage \
      google-auth openai httpx structlog tenacity python-jose[cryptography] \
      opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi \
      opentelemetry-instrumentation-sqlalchemy opentelemetry-instrumentation-redis

# ---- runtime layer ----
FROM base AS runtime
COPY --from=deps /usr/local /usr/local
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN useradd -m -u 10001 app && chown -R app /app
USER app

EXPOSE 8080
ENV PORT=8080

# Default command runs the API gateway.
# Override at deploy time:
#   workers/stt:  CMD ["uvicorn", "app.workers.stt_worker:app", "--host", "0.0.0.0", "--port", "8080"]
#   workers/llm:  CMD ["uvicorn", "app.workers.llm_worker:app", "--host", "0.0.0.0", "--port", "8080"]
#   outbox:       CMD ["python", "-m", "app.workers.outbox_sweeper"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
