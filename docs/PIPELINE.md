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

## Phase 2 — Backend scaffold *(next)*

Planned:
- `backend/` FastAPI app with API + workers
- Pluggable `STTProvider` / `LLMProvider` ports + OpenAI + mock impls
- Postgres models + Alembic
- Pub/Sub publisher with outbox sweeper
- GCS signed-URL helper
- OpenTelemetry tracing
- pytest unit + integration suite

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
