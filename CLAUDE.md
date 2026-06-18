# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A reference implementation of an AI task-processing platform: **audio → STT → LLM summary → queryable result**. Built for a system-design assignment, scoped as a production-shaped GCP deployment. Read `ARCHITECTURE.md` first — it is the source of truth for component boundaries, the state machine, and ADRs.

## Tech stack

- **Backend:** FastAPI (Python 3.12), Pydantic v2, async SQLAlchemy + Alembic, OpenTelemetry
- **Frontend:** Next.js 15 (App Router, TS), Tailwind
- **Data:** Cloud SQL Postgres 16, Memorystore Redis, GCS
- **Messaging:** GCP Pub/Sub (per-stage topics + DLQ)
- **AI providers:** OpenAI Whisper + GPT-4o-mini default; Vertex AI alt; mock impls for tests. All behind the `STTProvider` / `LLMProvider` ports in `backend/app/providers/`.
- **Infra:** Terraform → Cloud Run (multi-region), Global HTTPS LB + Cloud Armor + Cloud CDN
- **CI/CD:** GitHub Actions, OIDC → GCP (no JSON keys), canary + auto-rollback

## Common commands

> Filled in as each phase lands. Treat absent commands as "not yet scaffolded" — check the phase log in `docs/PIPELINE.md` before assuming.

```bash
# Local dev (after Phase 4)
docker compose up                                # full stack with emulators + mocks
docker compose up postgres redis pubsub-emulator # data plane only

# Backend (after Phase 2)
cd backend
uv sync                                          # install deps
uv run uvicorn app.main:app --reload             # run API
uv run pytest                                    # all tests
uv run pytest tests/unit/test_state_machine.py::test_stt_done_transition  # single test
uv run ruff check . && uv run mypy app           # lint + types
uv run alembic upgrade head                      # apply migrations
uv run alembic revision --autogenerate -m "msg"  # new migration

# Frontend (after Phase 3)
cd frontend
pnpm install
pnpm dev
pnpm test                                        # vitest
pnpm test:e2e                                    # playwright (requires stack running)
pnpm lint && pnpm typecheck

# Infra (after Phase 5)
cd infra/envs/staging
terraform init && terraform plan
terraform apply

# Deploy (after Phase 6) — usually via CI, but manual:
gh workflow run deploy.yml -f env=staging
```

## Architecture rules that aren't obvious from the code

1. **The state machine is sacred.** Every task moves through `PENDING_UPLOAD → QUEUED → STT_RUNNING → STT_DONE → LLM_RUNNING → DONE | FAILED`. Workers must use the upsert helper in `app/domain/state.py`; never raw `UPDATE` a status. Adding a stage = adding a topic + handler + state, never branching inside an existing worker.

2. **Outbox, not direct publish.** API writes task rows and the outbox event in the same Postgres tx. A sweeper publishes to Pub/Sub. Do NOT call `pubsub.publish()` from a request handler — it breaks the no-orphan-event guarantee. (Workers publishing to the *next* stage are different — they're already idempotent on `(task_id, stage, attempt_id)`.)

3. **Providers are ports.** Anything model-related goes through `STTProvider` / `LLMProvider` in `app/providers/`. Never import an SDK (`openai`, `google.cloud.aiplatform`) outside an adapter. This is what makes the plug-in-tasks bonus real.

4. **Idempotency keys.** Every write from a worker carries `(task_id, stage, attempt_id)` and relies on a `UNIQUE` constraint. Pub/Sub is at-least-once — assume duplicate delivery.

5. **Trace context across Pub/Sub.** When publishing, copy `traceparent` into message attributes. When subscribing, restore it before doing any other work. One user action = one trace from upload to summary.

6. **No bytes through the API.** Audio uploads use V4 signed URLs to GCS. The API never touches the blob stream. Don't add an upload endpoint that does.

7. **Per-tenant filtering at the repository, not the route.** All queries flow through repository methods that take a `tenant_id` and inject it into the `WHERE`. Bypassing the repo is how tenant isolation breaks.

8. **Migrations are expand-then-contract.** Never write a destructive migration that gates on a code deploy. Old + new code must both work against the new schema.

## Environments

- **Dev:** docker-compose locally with the Pub/Sub + GCS emulators and mock providers. No GCP creds needed.
- **Staging:** small GCP project, real services, real provider keys (low quotas), open to engineering only.
- **Prod:** multi-region GCP project, Cloud Armor on, canary deploys, PagerDuty wired.

## Where things live

- `ARCHITECTURE.md` — diagrams, decisions, SLOs.
- `docs/adr/` — one ADR per cross-cutting decision.
- `docs/runbooks/` — DLQ replay, region failover, secret rotation, rollback.
- `docs/PIPELINE.md` — chronological log of build phases (kept in sync as phases land).
- `infra/envs/{staging,prod}/` — per-env Terraform; modules are shared.

## When you change a provider

Update `app/providers/{stt,llm}/{provider}.py` + add a test in `backend/tests/providers/` against a recorded fixture (do NOT hit the real API in CI). If you add a new provider, register it in `app/providers/registry.py` — that's the only place the dispatcher looks.

## Things to avoid

- Calling AI SDKs directly outside `app/providers/`.
- Publishing to Pub/Sub from a request handler (use the outbox).
- Adding a new task status without updating the state machine + a migration.
- Putting secrets in `.env` (only `.env.example` is committed); use Secret Manager.
- Running `terraform apply` against prod from a laptop — CI only.
