# syntax=docker/dockerfile:1.7
FROM python:3.14-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ---- deps layer ----
FROM base AS deps
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---- runtime ----
FROM base AS runtime
COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=deps /usr/local/bin /usr/local/bin
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd -m -u 10001 app && chown -R app /app
USER app
EXPOSE 8080
ENV PORT=8080
HEALTHCHECK --interval=20s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:${PORT}/healthz || exit 1
# Default = API gateway. Override CMD for workers:
#   stt-worker: ["uvicorn","app.workers.stt_worker:app","--host","0.0.0.0","--port","8080"]
#   llm-worker: ["uvicorn","app.workers.llm_worker:app","--host","0.0.0.0","--port","8080"]
#   sweeper:    ["python","-m","app.workers.outbox_sweeper"]
#   migrate:    ["alembic","upgrade","head"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
