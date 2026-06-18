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

Planned:
- `frontend/` Next.js 15 App Router
- Upload page using signed URL
- Realtime task status (SSE)
- Results page

---

## Phase 4 — Local dev (`docker-compose`)

Planned:
- Postgres, Redis, Pub/Sub emulator, GCS emulator (fake-gcs-server), mock STT/LLM, API, worker(s), frontend.
- One-command boot, seeded data.

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

Planned:
- pytest unit + integration, contract tests for providers, vitest + playwright on frontend, k6 smoke for load.

---

## Phase 9 — Demo & deck

Planned:
- `docs/demo-script.md` (how to run the demo end-to-end).
- Outline for an interview slide deck (under `docs/deck.md`).
