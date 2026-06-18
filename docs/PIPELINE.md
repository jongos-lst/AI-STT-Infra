# Build Pipeline Log

Chronological record of every phase. Each entry lists what was produced, what to verify, and the commit it landed in.

---

## Phase 0 — Repo bootstrap

**Date:** 2026-06-18
**Status:** ✅ done

- `git init -b main`
- `.gitignore` covering Python, Node, Terraform, env files, GCP creds
- Empty `docs/` for runbooks + ADRs

---

## Phase 1 — Architecture & Claude guide

**Date:** 2026-06-18
**Status:** ✅ done

- `ARCHITECTURE.md` — system diagram, sequence diagram, deployment topology, CI/CD diagram, ADR table, SLOs, ports/adapters, security and observability strategy.
- `CLAUDE.md` — guidance for future Claude Code sessions: stack, common commands (filled per phase), invariants that aren't obvious from the code.
- This pipeline log.

**Verify:** read `ARCHITECTURE.md`; both Mermaid diagrams render in GitHub.

---

## Phase 2 — Backend scaffold

**Date:** 2026-06-18
**Status:** ✅ done

Delivered (42 Python files):
- **API (`app/api/`)**: `tasks` (POST create + signed URL, POST complete, GET), `health` (healthz + readyz), `deps` with tenant-aware session/repo/rate-limit dependencies, Pydantic v2 schemas with content-type allowlist.
- **Domain (`app/domain/task.py`)**: `Task` entity + `TaskStatus` enum + explicit adjacency-list state machine. Re-entering RUNNING states allowed (worker retries); leaving terminal states denied.
- **Providers (`app/providers/`)**: `STTProvider` + `LLMProvider` ports; impls for OpenAI Whisper, OpenAI GPT-4o-mini, mock STT, mock LLM (with streaming); `registry.py` is the only dispatch site.
- **Infra (`app/infra/`)**: async SQLAlchemy engine + `session_scope`, ORM models matching migration 0001, tenant-aware `TaskRepository` + `OutboxRepository` + `AuditRepository`, Redis cache/rate-limit helper, GCS V4 signed URLs, Pub/Sub publisher.
- **Workers (`app/workers/`)**: `stt_worker` + `llm_worker` as FastAPI services receiving Pub/Sub push (idempotent UPSERT on `(task_id, attempt_id)`); `outbox_sweeper` long-loop with `FOR UPDATE SKIP LOCKED`.
- **Cross-cutting (`app/core/`)**: typed settings, structlog with trace-id injection, OTel init with trace-context propagation across Pub/Sub, JWT auth with dev bypass, domain-error → HTTP mapping.
- **Migrations**: Alembic 0001 covering `tasks`, `transcripts`, `summaries`, `outbox` (with partial index on unpublished), `audit_log`.
- **Tests**: 23 unit tests — state machine (10 valid + 5 invalid transitions + terminal check), task entity (3), mock providers (4 incl. streaming). **All green.**
- **Tooling**: `pyproject.toml` (uv-compatible, ruff + mypy strict), multi-stage `Dockerfile`, `.dockerignore`, `.env.example`, `README.md`.

**Verified locally:**
- 42/42 files compile clean (`py_compile`).
- `pytest tests/unit` → **23 passed**.
- `TestClient` boot: `GET /healthz` → 200, `GET /` → 200, `POST /v1/tasks` reaches the rate-limit dependency (Redis not running yet — expected; comes in Phase 4).

---

## Phase 3 — Frontend scaffold

**Date:** 2026-06-18
**Status:** ✅ done

Delivered (Next.js 15 + TypeScript + Tailwind):
- **Upload flow** (`src/components/UploadCard.tsx`): hash → POST `/v1/tasks` → PUT directly to GCS via signed URL → POST `.../complete` → redirect to status page. Bytes never traverse the API.
- **Status page** (`src/app/tasks/[id]/page.tsx` + `TaskView.tsx`): polls every 1.5 s, stops on terminal status, shows transcript + summary as they appear; clean error state.
- **Typed API client** (`src/lib/api.ts`): typed `ApiClientError` carrying HTTP status + parsed `{error: {code, message}}` body.
- **Shared types** (`src/lib/types.ts`): mirror the Pydantic schemas; `TERMINAL_STATUSES` constant matches the backend.
- **UI primitives**: `StatusBadge`, `ProgressBar` driven by `STATUS_LABEL` / `STATUS_TONE` / `PROGRESS_PERCENT` tables.
- **Tests**: 7 vitest unit tests (api client, sha256 with FileReader polyfill, status tables monotonicity) + 1 Playwright e2e (happy path upload → DONE).
- **Tooling**: standalone-output Dockerfile, security headers in `next.config.ts`, `vitest.config.ts`, `playwright.config.ts`.

**Verified locally:**
- `npm run typecheck` clean.
- `npm test` → **7 passed**.
- `npm run build` → 4 routes generated, 102 kB first-load JS.

**Known notes:**
- ESLint config creation blocked by a local config-protection hook; `next lint` will create one on first run.
- Playwright e2e expects the full docker-compose stack (Phase 4) — written but not executed yet.

---

## Phase 4 — Local dev (`docker-compose`)

**Date:** 2026-06-18
**Status:** ✅ done — full stack running, end-to-end task pipeline proven

**11 containers up under `docker compose up --build`:**

| Tier | Services |
|---|---|
| Data plane | `postgres`, `redis`, `pubsub-emulator`, `gcs` (fake-gcs-server) |
| One-shot init | `db-migrate` (alembic upgrade head), `init-pubsub` (topics + push subs + DLQ + 5-attempt redelivery), `init-gcs` (buckets + CORS rules) |
| Backend | `api`, `stt-worker`, `llm-worker`, `outbox-sweeper` |
| Frontend | `frontend` |

**Boot order** is enforced by `service_completed_successfully` on the init containers. App services don't start until migrations have run and topics/buckets exist.

**End-to-end smoke test (via curl):** create task → POST audio bytes to fake-gcs → POST `/complete` → poll. Result:
```
poll 1: QUEUED
poll 2: DONE
```
DB rows confirm transcript and summary saved; objects confirmed in both buckets (`audio` + `transcripts`).

**Dev/prod parity break (documented):** real GCS signed URLs use `PUT`; fake-gcs-server requires `POST` to `/upload/storage/v1/b/<bucket>/o?uploadType=media`. The API response now carries `upload_method` so the same frontend code works against both — divergence is isolated to one branch in `app/infra/gcs.py:signed_upload_url`.

**Other fixes during bring-up:**
- Simplified `backend/Dockerfile` to use `requirements.txt` for a cache-friendly deps layer.
- `app/infra/gcs.py` now uses `AnonymousCredentials` when `STORAGE_EMULATOR_HOST` is set.
- CORS is applied per-bucket via the `init-gcs` script (fake-gcs-server has no CLI CORS flag).
- `outbox-sweeper` healthcheck disabled in compose (it has no HTTP server).

**Verified:** 7/7 frontend tests still green, full task pipeline observed end-to-end, all 11 containers report `healthy` or `running` after stabilization.

**Open in a browser:**
- http://localhost:3000 — frontend (drag in a `.wav`)
- http://localhost:8080/docs — Swagger UI
- http://localhost:4443 — fake-gcs-server

---

## Phase 5 — Terraform on GCP

Planned:
- Modules: network, cloud-run, cloud-sql, pubsub, gcs, secret-manager, observability, edge (LB + Armor + CDN).
- Envs: staging, prod (multi-region asia-east1 + us-central1).

---

## Phase 6 — GitHub Actions CI/CD

Planned:
- lint → test → security scan → build → push GAR → terraform plan → deploy staging → e2e → manual gate → canary prod → auto-rollback.

---

## Phase 7 — Observability

Planned:
- OTel SDK in every service, trace propagation across Pub/Sub.
- Cloud Monitoring custom metrics, SLO dashboards, alert policies, runbooks.

---

## Phase 8 — Tests

**Date:** 2026-06-18
**Status:** ✅ done — backend 40 / frontend 7 vitest + Playwright e2e green

| Tier | Count | Notes |
|---|---|---|
| Backend unit                  | 26 | state machine, task entity, mock providers, metrics with `InMemoryMetricReader` |
| Backend provider contracts    | **6 new** | OpenAI Whisper + GPT-4o-mini adapters via `respx` — verifies response parsing, retry behaviour, 4xx/5xx → `ProviderError` mapping, streaming SSE chunks |
| Backend integration           | **8 new** | repository CRUD, **tenant isolation** (wrong tenant → `NotFoundError`), state transitions across the wire, transcript UPSERT idempotency, outbox row visible to sweeper SELECT, full POST /v1/tasks → GCS → complete → DONE through the gateway |
| Frontend unit (vitest)        | 7 | api client, sha256, status tables |
| Frontend e2e (Playwright)     | **1 live** | runs against `localhost:3000`, walks the upload flow in Chromium, asserts the status badge flips to "Done" and the summary panel renders |

**CI**: `backend-ci.yml` now runs unit + provider + integration repository tests against the existing Postgres + Redis service containers. End-to-end integration is reserved for the staging e2e job (`e2e.yml`).

**Fixes during this phase:**
- `pyproject.toml` now declares the `integration` marker, sets `asyncio_default_*_loop_scope = "session"` so async DB connections survive cross-test cleanup.
- `e2e/upload.spec.ts`: tightened locator to dodge Playwright strict-mode (Status badge "Done" matched the same text in the Summary panel).
- Whisper test patches `app.infra.gcs.open_for_read` (the source module) rather than the lazy import inside the adapter.

---

## Phase 9 — Demo & deck

**Date:** 2026-06-18
**Status:** ✅ done — final phase

Delivered:
- `docs/demo-script.md` — 10-minute live demo broken into 7 acts (setup off-camera → frame the problem → live upload → state machine → observability → CI/CD → tradeoffs → close), with explicit recovery moves if something breaks on stage.
- `docs/deck.md` — 15-slide outline for the interview presentation: cover, problem-in-a-sentence, three system diagrams, state machine, sequence diagram, scaling story, fault tolerance, multi-region topology, observability, CI/CD, tradeoffs (3 ADRs), what I'd build next, demo handoff, prepared Q&A answers.
- `README.md` rewritten as a real entry point — what's here, architecture-in-one-minute, the 8 invariants, stack at a glance, develop quickstart, deliberate non-goals.

---

## Final state

- **9 phases · 10 commits on `main` · pushed to GitHub.**
- **Tests:** 40 backend (26 unit + 6 provider contracts + 8 integration) + 7 frontend vitest + 1 live Playwright e2e = **48 passing**.
- **Infra:** 10 Terraform modules, 3 envs all `validate` clean.
- **CI/CD:** 8 workflows, all `actionlint` clean.
- **Docs:** ARCHITECTURE (8 Mermaid diagrams) + CLAUDE + PIPELINE + 5 runbooks + demo + deck + READMEs.

Pipeline log will be amended as the system evolves. The repository is in a state where a new collaborator can `git clone && docker compose up` and have the full stack reach DONE in under two minutes.
