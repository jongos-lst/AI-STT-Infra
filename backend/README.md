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

## Worker retries and timestamps

Run `alembic upgrade head` before deploying this version. Migration `0002` only
adds `stt_failures` and `llm_failures`, both defaulting to zero. Existing rows and
inserts from the previous application version remain compatible. The retry fix
requires all worker instances to be updated; an old worker still has the old
failure behavior.

Each stage persists its failed-execution count in PostgreSQL. A transient error
keeps the task in that stage's RUNNING state and returns HTTP 500 so Pub/Sub can
retry with its configured backoff. The count survives process restarts and does
not depend on Pub/Sub's best-effort `deliveryAttempt`. Provider adapters may have
their own bounded internal retries before one failed execution is counted.

At `WORKER_MAX_FAILURES` (default 5), the worker atomically commits FAILED, the
last error, and one `tasks.dlq` outbox event with a `failed_stage` attribute. It
then acknowledges the push so the broker does not dead-letter the same handled
failure as well. Pub/Sub's configured dead-letter policy remains a fallback. Its delivery count
is best-effort, so it can forward a message before the application budget is
reached, including after ordinary provider failures as well as transport,
process, or database failures. Such tasks remain nonterminal and require the
[DLQ runbook](../docs/runbooks/dlq-replay.md). Keep the application budget no
higher than the subscription's delivery budget (both default to 5); changing
`WORKER_MAX_FAILURES` does not reconfigure Pub/Sub. This does not guarantee that
every broker-dead-lettered task has already reached FAILED. As with every outbox
publication, delivery is at-least-once; DLQ consumers should deduplicate by task
ID and stage.

Short row locks serialize state changes and accepted result writes. Provider
calls remain outside transactions. Completed/failed tasks and late deliveries
cannot be reopened or overwrite a winning result. A successful retry clears the
previous error. Every persisted state transition advances `updated_at`, while
`created_at` remains unchanged.

Worker regression tests use real PostgreSQL with local provider/storage fixtures:

```bash
pytest tests/integration/test_repository.py tests/integration/test_workers.py
```

### Provider SDK compatibility

OpenAI SDK support is constrained to `>=1.55,<3` in both dependency manifests.
The existing provider contract fixtures intercept the SDK's `httpx` transport;
SDK 3 uses `httpx2`, which bypasses those fixtures. SDK 2.54.0 passes the existing
contracts. Keep the major-version constraint until the adapters and offline
fixtures are validated together on SDK 3; no live model calls are required for
these tests.
