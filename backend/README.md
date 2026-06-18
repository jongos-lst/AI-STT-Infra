# backend

FastAPI service that exposes the public API gateway **and** the Pub/Sub-driven workers. One image, three entrypoints (gateway / STT worker / LLM worker / outbox sweeper).

See [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for the full design, [`../CLAUDE.md`](../CLAUDE.md) for invariants.

## Local

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8080
```

In another terminal:

```bash
uv run uvicorn app.workers.stt_worker:app --reload --port 8081
uv run uvicorn app.workers.llm_worker:app --reload --port 8082
uv run python -m app.workers.outbox_sweeper
```

The full stack (Postgres, Redis, Pub/Sub emulator, GCS emulator, mock providers) is in the root `docker-compose.yml` (Phase 4).

## Test

```bash
uv run pytest                                 # all
uv run pytest tests/unit                      # fast
uv run pytest -m integration                  # needs docker-compose up
uv run ruff check . && uv run mypy app
```

## Layout

```
app/
  api/         routes — tasks, health
  core/        config, auth, logging, OTel
  domain/      task entity + state machine (source of truth)
  providers/   STTProvider + LLMProvider ports, impls, registry
  infra/       Postgres repo, Redis, GCS signed URLs, Pub/Sub publisher
  workers/     stt_worker, llm_worker, outbox_sweeper
  main.py      gateway entrypoint
```
