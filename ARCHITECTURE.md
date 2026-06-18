# AI Processing Platform — Architecture

> A scalable, observable, multi-region AI task platform on GCP. Audio → STT → LLM summary → queryable result.

**Target SLOs:** API p99 < 300 ms (excluding model latency) · Task end-to-end p95 < 90 s for ≤ 10 min audio · Availability 99.9 % monthly.

---

## 1. System Architecture

> Two views: the **request path** (what a user touches) and the **async pipeline** (what processes the task). Separating them keeps each diagram readable.

### 1a. Request path — user → API

```mermaid
flowchart LR
  U([User browser])

  subgraph Edge["🌐 Edge (global)"]
    direction TB
    LB["Global HTTPS LB<br/>+ Cloud Armor WAF"]
    CDN["Cloud CDN"]
  end

  subgraph Compute["⚡ Cloud Run (multi-region)"]
    direction TB
    FE["Next.js 15<br/>Frontend"]
    API["FastAPI<br/>Gateway"]
  end

  subgraph Sync["💾 Sync data plane"]
    direction TB
    PG[("Cloud SQL<br/>Postgres HA")]
    RC[("Memorystore<br/>Redis")]
    GCS[("GCS<br/>audio + transcripts")]
  end

  Outbox[["Outbox table<br/>→ Pub/Sub"]]:::ghost

  U -- 1 page --> CDN --> FE
  U -- 2 API call --> LB --> API
  U == 3 PUT audio (signed URL) ==> GCS

  API -- read/write --> PG
  API -- cache --> RC
  API -- sign URL --> GCS
  API -. tx-local write .-> Outbox

  classDef ghost fill:#fff,stroke:#999,stroke-dasharray:4 3,color:#555;
  linkStyle 2 stroke:#1f7a1f,stroke-width:3px;
```

**Read it as:** ① static assets come from CDN, ② API calls hit the global LB, ③ audio bytes go **directly** to GCS via a signed URL — they never traverse the API. The dashed Outbox is the bridge to diagram 1b.

### 1b. Async pipeline — Pub/Sub → workers → providers

```mermaid
flowchart LR
  Outbox[["Outbox sweeper"]]:::ghost

  subgraph Q1["📨 Stage 1 queue"]
    T1[/"topic: stt.requested"/]
  end

  STT["STT Worker<br/>Cloud Run"]

  subgraph Q2["📨 Stage 2 queue"]
    T2[/"topic: llm.requested"/]
  end

  LLM["LLM Worker<br/>Cloud Run"]

  DLQ(["Dead-letter<br/>topic"]):::dlq

  subgraph Providers["🔌 Pluggable provider ports"]
    direction TB
    SP["STTProvider<br/>• OpenAI Whisper<br/>• Vertex Chirp<br/>• Mock"]
    LP["LLMProvider<br/>• GPT-4o-mini<br/>• Gemini<br/>• Mock"]
  end

  subgraph State["💾 Persistence"]
    direction TB
    PG2[("Postgres")]
    GCS2[("GCS")]
    RC2[("Redis")]
  end

  Outbox --> T1 --> STT
  STT --> SP
  STT -- transcript --> GCS2
  STT -- status + transcript --> PG2
  STT -- publish next --> T2

  T2 --> LLM
  LLM --> LP
  LLM -- summary --> PG2
  LLM -- stream tokens --> RC2

  T1 -. 5 nacks .-> DLQ
  T2 -. 5 nacks .-> DLQ

  classDef ghost fill:#fff,stroke:#999,stroke-dasharray:4 3,color:#555;
  classDef dlq fill:#ffe5e5,stroke:#c33;
```

**Read it as:** outbox publishes → STT worker consumes, calls a provider, writes results, then publishes to the LLM topic → LLM worker consumes, summarizes, persists. Either stage drops to DLQ after 5 failures.

### 1c. Cross-cutting — security & observability

```mermaid
flowchart LR
  subgraph App["All services (FE / API / STT / LLM)"]
    A1[Service]
  end

  subgraph Sec["🔐 Security"]
    direction TB
    SM["Secret Manager"]
    IAM["IAM + Workload Identity"]
    AR["Cloud Armor"]
  end

  subgraph Obs["📊 Observability"]
    direction TB
    OT["OpenTelemetry SDK<br/>(traces + metrics + logs)"]
    CL["Cloud Logging"]
    CT["Cloud Trace"]
    CM["Cloud Monitoring"]
    AL["Alerts<br/>→ PagerDuty / Slack"]
  end

  A1 -- assume identity --> IAM
  A1 -- fetch keys --> SM
  AR -. WAF .-> A1

  A1 --> OT
  OT --> CL
  OT --> CT
  OT --> CM
  CM --> AL
```

### Logical boundaries

| Service | Responsibility | Stateless? |
|---|---|---|
| **Next.js frontend** | Upload UI, task status polling, results view, auth (Firebase Auth / NextAuth) | yes |
| **API Gateway (FastAPI)** | Auth, signed GCS upload URLs, task CRUD, publishes to Pub/Sub, read API | yes |
| **STT Worker** | Subscribes `stt.requested`, calls provider, writes transcript, publishes `llm.requested` | yes |
| **LLM Worker** | Subscribes `llm.requested`, calls provider, writes summary, updates task | yes |
| **Provider adapter** | Abstract interface, concrete impls per provider, **plug-in registry** for new tasks | yes |
| **Postgres** | Source of truth: tasks, transcripts, summaries, audit log | stateful |
| **Redis** | Hot-path cache (result lookup, idempotency keys, rate limit counters) | stateful |
| **GCS** | Audio blobs + raw transcript JSON | stateful |
| **Pub/Sub** | Decoupled queues, per-stage topics, DLQ on 5 redeliveries | managed |

---

## 2. Sequence Diagram

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant FE as Next.js
  participant API as FastAPI
  participant DB as Postgres
  participant GCS as GCS
  participant PS as Pub/Sub
  participant STT as STT Worker
  participant LLM as LLM Worker
  participant W as Whisper
  participant G as GPT

  U->>FE: select audio + click upload
  FE->>API: POST /v1/tasks {filename, sha256, size}
  API->>DB: INSERT task (status=PENDING_UPLOAD)
  API->>GCS: signV4(PUT, 15 min)
  API-->>FE: {task_id, upload_url}
  FE->>GCS: PUT audio (resumable)
  FE->>API: POST /v1/tasks/{id}/complete
  API->>DB: UPDATE status=QUEUED
  API->>PS: publish stt.requested {task_id}
  API-->>FE: 202 Accepted

  PS->>STT: deliver msg (at-least-once)
  STT->>DB: UPDATE status=STT_RUNNING (idempotent on attempt_id)
  STT->>GCS: download audio
  STT->>W: transcribe
  W-->>STT: transcript
  STT->>GCS: put transcript.json
  STT->>DB: INSERT transcript, status=STT_DONE
  STT->>PS: publish llm.requested {task_id}
  STT-->>PS: ack

  PS->>LLM: deliver msg
  LLM->>DB: UPDATE status=LLM_RUNNING
  LLM->>DB: SELECT transcript
  LLM->>G: summarize (streaming)
  G-->>LLM: summary tokens
  LLM->>DB: INSERT summary, status=DONE
  LLM-->>PS: ack

  loop polling or SSE
    FE->>API: GET /v1/tasks/{id}
    API->>Redis: GET task:{id}
    alt cache hit
      Redis-->>API: result
    else miss
      API->>DB: SELECT
      API->>Redis: SETEX 60s
    end
    API-->>FE: status + (summary if DONE)
  end
```

---

## 3. Technology Selection & Rationale

| Layer | Choice | Why | Trade-off |
|---|---|---|---|
| Frontend | **Next.js 15 (App Router, TS)** | SSR for SEO, RSC for fast initial load, file-based routing, easy Cloud Run deploy | Heavier than Vite SPA — acceptable for a real product surface |
| Backend | **FastAPI + Python 3.12** | Async I/O matches network-bound AI calls; Pydantic v2 = strong contracts; OpenAPI free; ML ecosystem | Python GIL — mitigated by async + multiple Cloud Run instances |
| Workers | **Cloud Run (request-driven Pub/Sub push)** | Scale to zero, per-request billing, no cluster ops | Cold start ~1 s — pre-warm via min-instances=1 in prod |
| Queue | **Pub/Sub** | Managed, infinite scale, native DLQ, push to Cloud Run | Vendor lock-in — abstracted behind a `MessageBus` interface |
| Primary DB | **Cloud SQL Postgres 16 HA** | ACID, JSONB for flexible result shapes, regional HA failover, mature tooling | Costlier than Firestore — needed for joins + transactional state machine |
| Cache | **Memorystore Redis** | Sub-ms latency, idempotency keys, rate limits, hot result cache | Extra moving part — kept small (1 GB) |
| Blob | **GCS** | Cheap, signed URLs offload upload bandwidth from API, lifecycle to coldline | Eventual consistency on bucket listings — irrelevant here |
| Secrets | **Secret Manager + Workload Identity** | No key files in containers, audit log, rotation | Slight lookup overhead — cached on cold start |
| Edge | **Global HTTPS LB + Cloud Armor + Cloud CDN** | Multi-region, WAF, anycast, DDoS protection | Costs ~$18/mo idle — required for SLO |
| AI | **OpenAI (default) + Vertex AI (alt) + Mock (test)** behind `STTProvider` / `LLMProvider` ports | Pluggable, vendor-neutral, mockable in tests | Each provider needs its own retry/error mapping |
| IaC | **Terraform** | Multi-cloud-portable, mature GCP provider, plan/apply review | Slower than Pulumi for Python folks — chosen for ecosystem |
| CI/CD | **GitHub Actions + OIDC to GCP** | Free for public repos, no long-lived keys, matrix builds | Limited to 6h job — fine for this pipeline |
| Observability | **OpenTelemetry → Cloud Logging/Trace/Monitoring** | Vendor-neutral SDK, trace context propagated through Pub/Sub | One more sidecar in workers — worth it |

---

## 4. Architecture Characteristics

### 4.1 Scalability

- **Horizontal everywhere:** API + workers on Cloud Run, autoscale 0 → 100 instances per region; concurrency=80 per instance.
- **Backpressure:** Pub/Sub absorbs spikes; workers pull at safe rate. Per-tenant token-bucket in Redis caps abuse.
- **Pre-signed uploads:** audio bytes never traverse the API — bandwidth scales with GCS.
- **Multi-region active-active:** `asia-east1` + `us-central1`. Global LB routes to nearest healthy region. DB stays single-region with cross-region read replica (write to primary).
- **Plug-in tasks:** new AI stages register a `TaskHandler` against a Pub/Sub topic — adding "translation" or "moderation" is one file + one topic.

### 4.2 Fault tolerance

- **At-least-once + idempotency:** every worker writes `(task_id, attempt_id)` upserts; retries safe.
- **Stage state machine:** explicit `PENDING_UPLOAD → QUEUED → STT_RUNNING → STT_DONE → LLM_RUNNING → DONE | FAILED`; resumable on crash.
- **DLQ:** after 5 redelivery attempts, message moves to DLQ topic → alert fires → human inspection.
- **Provider failover:** circuit breaker (PyBreaker); on open, route to alternate provider (e.g., Whisper → Vertex Chirp).
- **DB HA:** Cloud SQL regional HA with auto failover; PITR enabled (7-day window).
- **Graceful degradation:** if LLM is down, STT result still saved + queryable; LLM retried via DLQ replay tool.

### 4.3 Data consistency

- **Outbox pattern:** API writes task row + outbox event in one Postgres tx; a sweeper publishes to Pub/Sub. Guarantees "no orphan events" even if Pub/Sub publish fails.
- **Idempotency keys:** client-supplied + server-derived `(task_id, stage, attempt_id)` `UNIQUE` constraints.
- **Read-after-write:** results cached in Redis only after DB commit.
- **Schema migrations:** Alembic, forward-only, expand-then-contract.

### 4.4 Latency & performance

- **Streaming summaries:** LLM worker streams tokens to Redis pubsub; FastAPI SSE endpoint forwards to UI → user sees output in 1–2 s.
- **Whisper chunking:** audio > 10 min split into 5-min chunks processed in parallel, then merged.
- **Result cache:** completed tasks served from Redis (60 s) then Cloud CDN (1 h via signed Cache-Control).
- **Connection pooling:** PgBouncer sidecar in API (transaction mode).
- **Min instances:** API min=2 per region in prod to kill cold starts.

### 4.5 Security

- **Auth:** Firebase Auth (Google / passwordless). JWT verified at FastAPI middleware.
- **Per-tenant isolation:** every row carries `tenant_id`; row-level filters enforced in repository layer.
- **Signed upload URLs:** 15-min TTL, content-length + content-type bound.
- **Cloud Armor:** OWASP rules, geo-fence option, rate limit.
- **Encryption:** TLS 1.3 in transit; CMEK at rest for GCS + Cloud SQL.
- **Secrets:** Secret Manager + Workload Identity; no JSON key files. `.env.example` only in repo.
- **CSP + CORS:** strict allow-list on the frontend.
- **Audit log:** every write goes through a `audit_log` table; Cloud Audit Logs enabled on GCP services.

### 4.6 Observability

- **Tracing:** OTel SDK in all services; trace ID propagated via Pub/Sub message attributes — one trace covers upload → STT → LLM.
- **Logs:** structured JSON, `task_id` + `trace_id` on every line, shipped to Cloud Logging.
- **Metrics:** Cloud Monitoring custom metrics — `task_duration_seconds{stage}`, `provider_latency_seconds{provider}`, `queue_depth`, `dlq_size`.
- **SLO dashboards:** task success rate, p95 end-to-end, API availability.
- **Alerts:** DLQ > 0, error rate > 1 %, p95 > 90 s, Cloud SQL CPU > 80 % → PagerDuty + Slack.
- **Tracing the model:** prompt + completion logged to a sampled `llm_audit` table (1 % sample, 30-day retention) for quality review.

---

## 5. Deployment & Operations

### 5.1 Topology

Three environments, **identical Terraform modules**, different tfvars. Diagrams kept separate so each is readable.

#### Dev — laptop, docker-compose

```mermaid
flowchart LR
  DEV([Developer])
  subgraph Compose["docker-compose"]
    direction TB
    LFE[Next.js dev server]
    LAPI[FastAPI uvicorn --reload]
    LSTT[STT worker]
    LLLM[LLM worker]
    LPG[(Postgres 16)]
    LRC[(Redis)]
    LPS[(Pub/Sub emulator)]
    LGCS[(fake-gcs-server)]
    LMOCK["Mock STT + LLM HTTP server"]
  end
  DEV --> LFE
  DEV --> LAPI
  LAPI --> LPG & LRC & LPS & LGCS
  LPS --> LSTT & LLLM
  LSTT --> LMOCK
  LLLM --> LMOCK
```

#### Staging — single GCP project, single region (`asia-east1`)

```mermaid
flowchart LR
  U([User / engineer])
  subgraph Stg["GCP project: ai-stt-staging"]
    direction TB
    SLB[Global LB] --> SFE[FE Cloud Run]
    SLB --> SAPI[API Cloud Run]
    SAPI --> SPG[(Cloud SQL zonal)]
    SAPI --> SRC[(Redis basic 1 GB)]
    SAPI --> SPS[/Pub/Sub topics/]
    SPS --> SSTT[STT worker]
    SPS --> SLLM[LLM worker]
  end
  U --> SLB
```

#### Prod — multi-region active-active

```mermaid
flowchart TB
  U([Users — global])
  LB["Global HTTPS LB<br/>Cloud Armor + Cloud CDN"]
  U --> LB

  subgraph RegionA["🌏 asia-east1"]
    direction TB
    FE_A[FE Cloud Run<br/>min=2]
    API_A[API Cloud Run<br/>min=2]
    STT_A[STT worker<br/>min=1]
    LLM_A[LLM worker<br/>min=1]
  end

  subgraph RegionB["🌎 us-central1"]
    direction TB
    FE_B[FE Cloud Run<br/>min=2]
    API_B[API Cloud Run<br/>min=2]
    STT_B[STT worker<br/>min=1]
    LLM_B[LLM worker<br/>min=1]
  end

  LB --> FE_A & API_A
  LB --> FE_B & API_B

  subgraph Shared["☁️ Shared regional data plane"]
    direction LR
    PG_P[(Cloud SQL HA<br/>primary @ asia-east1)]
    PG_R[(Read replica<br/>@ us-central1)]
    PS[(Pub/Sub — global)]
    GCS[(GCS<br/>dual-region)]
    RC[(Memorystore<br/>regional)]
    PG_P -. async replica .-> PG_R
  end

  API_A --> PG_P & RC & GCS & PS
  API_B --> PG_R & RC & GCS & PS
  STT_A --> PS
  STT_B --> PS
  LLM_A --> PS
  LLM_B --> PS
```

**Promotion path:** Dev → Staging (auto on merge) → Prod (manual gate + canary).

### 5.2 CI/CD

```mermaid
flowchart LR
  Dev(["Developer<br/>push / PR"]) --> A1["GitHub Actions"]
  A1 --> L["Lint<br/>ruff · mypy · eslint · tsc"]
  L --> T["Test<br/>pytest · vitest"]
  T --> SCA["Security scan<br/>pip-audit · npm audit<br/>trivy · gitleaks"]
  SCA --> B["Build images"]
  B --> P["Push to Artifact Registry<br/>signed via cosign"]
  P --> TF["terraform plan<br/>(PR comment)"]
  TF -- merge to main --> DS["Deploy staging<br/>via OIDC"]
  DS --> E2E["Playwright e2e<br/>vs staging"]
  E2E --> Tag["Git tag vX.Y.Z"]
  Tag --> Gate{"Manual<br/>approval"}
  Gate -- approve --> CAN["Canary<br/>10% prod traffic"]
  CAN --> Watch["Watch SLOs<br/>10 min window"]
  Watch -- healthy --> Full["Promote 100%"]
  Watch -- regression --> RB["Auto rollback<br/>(traffic split)"]
```

### 5.3 Versioning, release & rollback

- **SemVer tags** drive prod deploys; image tag = `${git_sha}-${semver}`.
- **Cloud Run revisions:** every deploy is an immutable revision. Rollback = `gcloud run services update-traffic --to-revisions <prev>=100`. Sub-30-second rollback.
- **DB migrations:** expand-then-contract; deploys never gate on contract step. Alembic runs in a one-shot Cloud Run Job before traffic shift.
- **Feature flags:** OpenFeature SDK + GCS-backed config; risky changes ship dark, ramp via flag.
- **Canary:** 10 % traffic for 10 min; auto-rollback if error rate > 1 % or p95 > 1.5× baseline.

---

## 6. Architecture Decision Record (summary)

| # | Decision | Alternatives | Why this |
|---|---|---|---|
| ADR-001 | FastAPI over Flask/Django | Flask (sync), Django (heavy) | Async fits AI I/O; Pydantic contracts |
| ADR-002 | Pub/Sub over RabbitMQ/Kafka | RMQ (ops), Kafka (overkill) | Managed, scale-to-zero, push to Cloud Run |
| ADR-003 | Cloud Run over GKE | GKE (powerful, ops-heavy) | Zero ops, scale to zero, fits workload profile |
| ADR-004 | Postgres over Firestore | Firestore (serverless) | Transactional state machine, joins, JSONB hybrid |
| ADR-005 | Pluggable providers via ports/adapters | Hard-coded OpenAI | Vendor risk, testability, plug-in tasks bonus |
| ADR-006 | OIDC GitHub→GCP over JSON keys | Service account JSON | No long-lived secrets, audit-friendly |
| ADR-007 | Terraform over Pulumi/gcloud | Pulumi (Python DSL) | Provider maturity, plan-review workflow |
| ADR-008 | OpenTelemetry over vendor SDK | Cloud Trace SDK only | Portability if we leave GCP |
| ADR-009 | Outbox pattern for publish | Direct publish | Avoid lost events on Pub/Sub blip |
| ADR-010 | Streaming LLM via SSE + Redis pubsub | Long-poll only | Perceived latency win for users |

---

## 7. Repository Layout

```
.
├── ARCHITECTURE.md
├── CLAUDE.md                  # Guidance for Claude Code agents
├── README.md
├── docker-compose.yml         # Local dev: full stack with emulators + mocks
├── .github/workflows/         # CI/CD pipelines
├── backend/                   # FastAPI service
│   ├── app/
│   │   ├── api/               # Routers (tasks, health, sse)
│   │   ├── core/              # Config, auth, logging, OTel
│   │   ├── domain/            # Entities, state machine
│   │   ├── providers/         # STTProvider, LLMProvider ports + impls
│   │   ├── infra/             # PG repo, Redis, Pub/Sub, GCS
│   │   ├── workers/           # stt_worker.py, llm_worker.py
│   │   └── main.py
│   ├── alembic/               # Migrations
│   ├── tests/
│   └── pyproject.toml
├── frontend/                  # Next.js 15
│   ├── src/app/
│   ├── src/components/
│   ├── src/lib/
│   ├── tests/                 # vitest + playwright
│   └── package.json
├── infra/                     # Terraform
│   ├── modules/
│   │   ├── network/
│   │   ├── cloud-run/
│   │   ├── cloud-sql/
│   │   ├── pubsub/
│   │   ├── gcs/
│   │   ├── secret-manager/
│   │   ├── observability/
│   │   └── edge/              # LB + Armor + CDN
│   └── envs/
│       ├── staging/
│       └── prod/
└── docs/
    ├── adr/                   # ADR-001 … ADR-010
    ├── runbooks/              # DLQ replay, region failover, secret rotation
    └── demo-script.md
```

---

## 8. What's NOT in scope (future work)

- Multi-cloud failover (only GCP today; abstractions are ready for AWS sibling).
- Self-hosted Whisper / open LLM on GPU pool (cost trigger: >2 M minutes/month).
- Per-tenant model fine-tuning + RAG.
- Real-time transcription (WebSocket streaming STT).
