# AI Processing Platform

Audio → STT → LLM summary → queryable result, end-to-end on GCP. A system-design exercise built as a production-shaped reference: scalable, observable, multi-region, with the CI/CD and runbooks that real operation needs.

```
docker compose up --build       # full stack — frontend, API, workers, Pub/Sub, Postgres, Redis, GCS — in ~90s
open http://localhost:3000      # drag in any .wav and watch it reach DONE
```

## What's here

| Directory | What | Status |
|---|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System + sequence + deployment diagrams · 10 ADRs · SLO targets | source of truth |
| [`CLAUDE.md`](CLAUDE.md) | Guidance for future agents — invariants that aren't obvious from the code | — |
| [`backend/`](backend) | FastAPI gateway + STT/LLM workers + outbox sweeper · Postgres + Pub/Sub + GCS | 40 tests passing |
| [`frontend/`](frontend) | Next.js 15 App Router · upload + status pages | 7 vitest + 1 Playwright e2e |
| [`infra/`](infra) | 10 Terraform modules · 3 envs (bootstrap / staging / prod) | all `validate` clean |
| [`.github/workflows/`](.github/workflows) | 8 GitHub Actions workflows · OIDC to GCP · canary + auto-rollback | `actionlint` clean |
| [`docs/runbooks/`](docs/runbooks) | DLQ replay · region failover · secret rotation · rollback · on-call handoff | paste-ready `gcloud` |
| [`docs/demo-script.md`](docs/demo-script.md) | 10-minute live demo with talking points | — |
| [`docs/deck.md`](docs/deck.md) | 15-slide interview deck outline | — |
| [`docs/PIPELINE.md`](docs/PIPELINE.md) | Chronological build log — every phase, every commit, every fix | — |

## Architecture in one minute

```
┌─────────────┐      signed URL       ┌───────┐
│  Browser    │ ────── PUT audio ────▶│  GCS  │
└─────┬───────┘                       └───┬───┘
      │ POST /v1/tasks (no bytes)         │
      ▼                                    ▼
┌─────────────┐  outbox  ┌──────┐  push  ┌──────────┐  ┌──────────┐
│  FastAPI    │ ────────▶│Pub/  │ ──────▶│STT worker│─▶│LLM worker│─▶ Postgres
│  Gateway    │          │ Sub  │        │ (Whisper)│  │ (GPT-4o) │
└─────┬───────┘          └──────┘        └──────────┘  └──────────┘
      │                      │
      ▼                      ▼ 5 nacks
   Postgres                Dead-letter ─▶ alert + runbook
```

Full diagrams (request path · async pipeline · cross-cutting · sequence · deployment topology · CI/CD): [`ARCHITECTURE.md`](ARCHITECTURE.md).

## The invariants

These are the rules that make the system safe under load. They're enforced in code (state machine, repository layer, idempotency keys) and documented in [`CLAUDE.md`](CLAUDE.md) for future maintainers.

1. The state machine is the source of truth — workers never raw-`UPDATE` task status.
2. Outbox, not direct publish — every event is committed in the same DB tx as the state change.
3. Providers are ports — vendor SDKs are only imported inside adapters.
4. Idempotency keys `(task_id, stage, attempt_id)` — Pub/Sub is at-least-once; duplicates are safe.
5. Trace context survives Pub/Sub — one user action = one trace from upload to summary.
6. No bytes through the API — audio goes directly to GCS via a signed URL.
7. Tenant filtering at the repository, not the route.
8. Expand-then-contract migrations — old and new code both work against the new schema.

## Stack

- **Backend**: Python 3.12 · FastAPI · async SQLAlchemy + Alembic · OpenTelemetry
- **Frontend**: Next.js 15 (App Router, TS) · Tailwind · standalone Cloud Run build
- **Data**: Cloud SQL Postgres 16 HA · Memorystore Redis · GCS dual-region
- **Messaging**: GCP Pub/Sub · per-stage topics · DLQ with 5-attempt redelivery
- **AI providers**: OpenAI Whisper + GPT-4o-mini (pluggable; mocks for tests; Vertex AI ready to drop in)
- **Infra**: Terraform · Cloud Run multi-region · Global HTTPS LB + Cloud Armor + Cloud CDN
- **CI/CD**: GitHub Actions · OIDC Workload Identity (no keys) · cosign keyless signing · canary + auto-rollback

## Develop

```bash
# Full stack
docker compose up --build

# Backend (in another terminal)
cd backend && uv sync && uv run pytest                            # 40 tests
uv run uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm test                            # 7 tests
npm run dev                                                       # http://localhost:3000
npx playwright test                                               # e2e against compose

# Terraform
./infra/scripts/tf.sh envs/staging plan                           # docker-wrapped, no host install
```

See [`docs/PIPELINE.md`](docs/PIPELINE.md) for the full chronological build log.

## What's not built (deliberately)

These were scoped out to keep the exercise tight; they're called out in `ARCHITECTURE.md § 8`:

- Multi-cloud failover (only GCP today; abstractions are ready for AWS sibling)
- Self-hosted Whisper / open LLM on GPU pool (cost trigger: > 2M minutes/month)
- Real-time transcription (WebSocket streaming STT)
- Per-tenant fine-tuning + RAG

## License

This is an interview exercise; no license is granted. Treat the code as illustrative.
