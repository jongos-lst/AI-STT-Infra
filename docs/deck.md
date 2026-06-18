# Interview deck — outline

Speak the slides, don't read them. Each is one minute, two max. The verbal track should answer "why this choice, not the obvious alternative."

---

## 1. Cover

> **AI Processing Platform**
> System design — audio → STT → LLM summary → query
> jongos-lst · github.com/jongos-lst/AI-STT-Infra

## 2. The problem in one sentence

"Build a platform that **scales under spike load**, **survives a region or provider outage**, and **can grow new AI tasks without rewriting**."

Three constraints — every slide that follows defends one of them.

## 3. Topology (paste system diagram 1a — request path)

Audience reads this slide for 30 seconds. Then say:

- Bytes **never traverse the API**. Signed URL → direct PUT to GCS. API scales without bandwidth being the limit.
- Outbox table is the contract between the synchronous and asynchronous worlds.

## 4. Topology (paste system diagram 1b — async pipeline)

- Per-stage Pub/Sub topic. Adding "translation" or "moderation" is a new topic + handler, never edits to an existing worker.
- 5-attempt redelivery → DLQ. DLQ has its own pull subscription for human inspection.

## 5. State machine

Single image of the seven states + edges. Talking points:

- The state machine is the source of truth — every worker calls `transition(current, target)` and never raw-`UPDATE`s status.
- Re-entering RUNNING states is allowed (worker retry on Pub/Sub redelivery); leaving terminal states is not.

## 6. Sequence diagram (paste from ARCHITECTURE.md § 2)

Walk the path with a finger. Land on two beats:

- Trace context is stamped into Pub/Sub message attributes — one user action = one trace from upload to summary.
- Read API hits Redis first; only on miss does it touch Postgres. Result is cached on terminal status.

## 7. Scaling story

| Dimension | Mechanism |
|---|---|
| User count up 10× | Cloud Run autoscale 0 → 100/region · 80 concurrent/instance |
| Audio size up | Signed URL offloads bytes from API · chunking inside STT adapter |
| New AI task type | New `XxxProvider` adapter + new Pub/Sub topic + new worker — no changes to existing services |
| New region | One row in `regions` list in `infra/envs/prod/main.tf` |

## 8. Fault tolerance

- At-least-once delivery + idempotency keys `(task_id, stage, attempt_id)` — duplicates are safe.
- DLQ with operator inspector — bad messages don't poison the queue.
- Circuit breaker per provider; failover to alternate adapter.
- Cloud SQL HA + cross-region replica · expand-then-contract migrations.

## 9. The diagram I'm most proud of (deployment topology)

Paste the multi-region prod diagram. Talking point:

- **Active-active across asia-east1 + us-central1.** Global LB picks nearest healthy region. Workers consume a global Pub/Sub topic — losing a region drops throughput, not correctness.

## 10. Observability (one screenshot)

Show the dashboard JSON rendered. Six alert policies, six runbooks. Talking point:

- We don't ship a system; we ship a system **and** the muscle memory to operate it. Each alert points at the runbook that fixes it.

## 11. CI/CD pipeline (paste diagram from ARCHITECTURE.md § 5.2)

Highlight three things:

- **OIDC, no JSON keys** anywhere.
- **Canary 10% with 10-minute SLO watch** — automated rollback if 5xx spikes.
- **Cosign-signed images + SBOM** — supply chain attested.

## 12. Tradeoffs (pull 3 from the ADR table)

| Decision | Alternative | Why we chose |
|---|---|---|
| Cloud Run over GKE | GKE | Scale-to-zero; cross when we need GPUs |
| Outbox pattern | Direct publish | Survives Pub/Sub blip |
| Ports/adapters for providers | Direct SDK calls | Vendor risk is the #1 AI-product mistake |

## 13. What I'd build next

- Self-hosted Whisper on GPU pool, triggered when minute-spend > $X / month
- Per-tenant fine-tuning + RAG retrieval pipeline (another stage in the same chain)
- Real-time streaming STT (WebSocket) for live captioning use case

## 14. Live demo (this slide is "switch to the laptop")

`docker compose up`. The 10-minute demo script under `docs/demo-script.md`.

## 15. Q&A — questions I've prepared for

- "Why not Kafka?" — Pub/Sub is push-to-Cloud-Run + managed DLQ. Kafka wins on throughput at scale we don't yet need.
- "What about cold starts?" — `min_instances=2` per region in prod kills them; cost ~$40/month per service.
- "How do you test the workers?" — provider adapters via `respx` (no real API), repository against live Postgres, end-to-end through the running gateway. 48 tests today.
- "How do you handle PII in audio?" — CMEK at rest + TLS in transit + signed-URL TTL + per-tenant audit log. Mention legal/compliance as a future RBAC scope.
- "What's the most expensive component?" — the LLM call. Mitigations: caching identical-transcript summaries, streaming UI to mask perceived latency, batching for non-interactive workloads.
