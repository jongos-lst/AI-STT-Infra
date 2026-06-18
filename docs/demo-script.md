# Demo script — 10 minutes

Run from a freshly-cloned repo. Each step lists the **command**, the **expected output**, and the **talking point** to deliver while the action runs.

---

## 0 — Setup (off camera, 1 min before the call)

```bash
git clone https://github.com/jongos-lst/AI-STT-Infra
cd AI-STT-Infra
docker compose up --build -d        # ~90s first time, ~10s after
```

When `docker compose ps` shows everything `(healthy)`, you're ready.

Have these tabs open:
- https://github.com/jongos-lst/AI-STT-Infra  (the repo, for diagrams)
- http://localhost:3000  (frontend)
- http://localhost:8080/docs  (Swagger)
- http://localhost:4443/storage/v1/b/ai-stt-dev-audio/o  (fake-gcs bucket listing)

Drop a small `.wav` on the desktop. A 30-second test clip is plenty.

---

## 1 — Frame the problem (60s, no commands)

> "We're shipping audio → STT → LLM summary → query, end-to-end on GCP. The interesting work isn't the AI calls — it's everything around them: scaling, fault tolerance, observability. Let me show you the system, then run a real upload, then walk through the tradeoffs."

Open `ARCHITECTURE.md` in the browser. Show the **three-view system diagram** (request path / async pipeline / cross-cutting).

> "Two paths. Request path: signed URL means audio bytes go directly to object storage, not through the API — that's how the API scales without bandwidth being a bottleneck. Async path: every stage is its own Pub/Sub topic so we can add tasks like translation later without changing existing code."

---

## 2 — Run the pipeline live (90s)

Open the **frontend** (`http://localhost:3000`).

Drag the `.wav` in, click **Process audio**. Narrate while it runs:

> "Watch the phase label: hashing (in-browser SHA-256, gives us idempotency) → reserving upload URL → uploading to storage (this PUT goes to fake-gcs-server in dev, real GCS in prod) → finalizing (the API moves the task to QUEUED inside a single Postgres transaction that also writes to the outbox table)."

Page redirects to the status view. It says `Queued` → `Done` within ~4 seconds.

Don't say anything for those four seconds. Let the experience land.

Once `Done` appears, expand the transcript and read the summary aloud:

> "Mock providers in dev — same interface as the real OpenAI Whisper and GPT-4o-mini adapters. To flip on real providers I change two env vars: STT_PROVIDER=openai-whisper, LLM_PROVIDER=openai-gpt. The state machine, the workers, the queue topology don't care."

---

## 3 — Show the state machine (60s)

Switch to a terminal:

```bash
docker compose exec postgres psql -U postgres -d ai_stt -c \
  "SELECT id, status, updated_at - created_at AS elapsed FROM tasks ORDER BY created_at DESC LIMIT 1;"
```

> "Single row, DONE, ~4 seconds end-to-end."

Now show the outbox:

```bash
docker compose exec postgres psql -U postgres -d ai_stt -c \
  "SELECT id, topic, published_at - created_at AS lag FROM outbox ORDER BY id DESC LIMIT 5;"
```

> "Two outbox rows per task — one for stt.requested, one for llm.requested. Lag is sub-second in dev. We alert on p95 > 30 s in prod."

---

## 4 — Show observability (90s)

```bash
docker compose logs outbox-sweeper --tail=10 | grep lag_seconds
```

> "Structured log + a typed OTel histogram. In prod that exports to Cloud Monitoring; in dev to stdout."

Open the **observability module**: `infra/modules/observability/main.tf`. Scroll to alert policies.

> "Six alert policies — DLQ depth, API 5xx, Cloud SQL CPU, task FAILED rate, outbox lag p95, provider errors. Each one routes to PagerDuty via a notification channel. Each one has a paste-ready runbook in `docs/runbooks/`."

Open `docs/runbooks/dlq-replay.md` briefly.

> "Each runbook follows the same shape: when to use, what to decide, paste-ready gcloud commands, how to verify, and an escape hatch if the runbook itself fails. Written for the on-call engineer who's been paged at 3am."

---

## 5 — Show the CD pipeline (90s)

Open `.github/workflows/deploy-prod.yml`.

> "Tag a release → build matrix → cosign-sign the images → manual approval gate → terraform apply → Alembic migration as a Cloud Run Job → canary 10% in both regions → 10-minute SLO watch → promote or auto-rollback."

Highlight the rollback job at the bottom:

> "If the watch detects regression, this job picks the previous revision per service per region and flips traffic. Sub-30-second rollback."

---

## 6 — Tradeoffs (60s, anchor to ADR table)

Switch to `ARCHITECTURE.md` § ADR table.

> "Three I'd defend on a whiteboard:
>
> - **Cloud Run over GKE** — for this workload (request-driven, scale-to-zero, no GPU), Cloud Run wins on operational cost. If we need GPUs for self-hosted Whisper later, this is the line I'd cross.
> - **Outbox pattern** — costs one extra Postgres row per task, but guarantees no orphan events even if Pub/Sub blips during a publish.
> - **Pluggable providers** — vendor lock-in is the single biggest mistake in AI products today. The `STTProvider`/`LLMProvider` ports take one engineer-day up front and saved us when OpenAI had that 4-hour outage last month."

---

## 7 — Close (30s)

> "47 unit + integration tests, 1 live Playwright e2e, multi-region terraform, automated canary with rollback, paste-ready runbooks. The whole thing boots from `docker compose up` in 90 seconds. Where would you like to go deeper?"

---

## Recovery — if things break on stage

| Symptom | Fix |
|---|---|
| `frontend` won't render | `docker compose restart frontend` then refresh |
| Upload returns 400 | Check `curl http://localhost:4443/storage/v1/b/ai-stt-dev-audio/o` — buckets created? Re-run `init-gcs` if missing |
| Task stuck QUEUED | `docker compose logs outbox-sweeper` — probably can't reach Pub/Sub emulator |
| Anything else | Switch to the GitHub repo and walk the architecture diagrams — they're a complete demo by themselves |
