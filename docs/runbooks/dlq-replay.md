# Runbook — DLQ replay

**When to use.** The `ai-stt DLQ has messages` alert fired, or you see `tasks.dlq` non-zero in the dashboard.

## Decision

Before replaying, find out **why** a task ended up in the DLQ:

1. Open the failed task in Cloud Logging: `resource.type="cloud_run_revision" AND jsonPayload.task_id="<id>" AND severity>=ERROR`.
2. Identify the failure class. Common ones:
   - **Provider 5xx / rate limit** — transient, safe to replay.
   - **Bad input** (e.g. corrupted audio, unsupported codec) — replay will fail again. Mark the task `FAILED` instead.
   - **State machine violation** — bug, file an issue; do not replay until fixed.
   - **DB constraint failure** — investigate the data, the schema, or both.

If you can't decide in 5 minutes, page the on-call engineer and pull the message into a debugging script instead of replaying blind.

## Steps

```bash
PROJECT=ai-stt-prod
DLQ_SUB=tasks.dlq-inspector
STT_TOPIC=stt.requested
LLM_TOPIC=llm.requested

# 1. Drain a batch from the inspector subscription into a local file.
gcloud pubsub subscriptions pull "$DLQ_SUB" \
  --project="$PROJECT" \
  --limit=50 --auto-ack \
  --format='json(message.attributes,message.data,ackId)' > /tmp/dlq.json

# 2. For each message, decide and re-publish to the original topic.
jq -c '.[]' /tmp/dlq.json | while read -r msg; do
  ATTRS=$(echo "$msg" | jq -r '.message.attributes | to_entries | map("\(.key)=\(.value)") | join(",")')
  DATA=$(echo "$msg"  | jq -r '.message.data' | base64 -d)
  # Look at the payload to pick the right topic. STT comes first, so when in
  # doubt re-queue at the start of the pipeline.
  TOPIC="$STT_TOPIC"
  gcloud pubsub topics publish "$TOPIC" \
    --project="$PROJECT" \
    --message="$DATA" \
    --attribute="$ATTRS"
done
```

For a single known-good task ID:

```bash
TASK_ID=<uuid>
gcloud pubsub topics publish "$STT_TOPIC" --project="$PROJECT" \
  --message="{\"task_id\":\"$TASK_ID\"}" \
  --attribute="tenant_id=<tenant>"
```

To declare a task permanently failed instead:

```sql
UPDATE tasks
SET status='FAILED', error='unrecoverable (dlq-replay manual override)', updated_at=now()
WHERE id='<uuid>' AND status NOT IN ('DONE','FAILED');
```

## Verify

- `gcloud pubsub subscriptions describe "$DLQ_SUB" --format='value(numUndeliveredMessages)'` returns 0.
- Replayed tasks reach `DONE` within the usual time (check the dashboard, **API request rate by service** + **Pub/Sub backlog**).
- The `ai-stt DLQ has messages` alert auto-resolves within 5 minutes.

## If this runbook itself fails

- Cannot pull messages → check `roles/pubsub.subscriber` on your account, or the OIDC SA on automation.
- Re-published messages immediately bounce back → bug is *not* transient. Stop, file an issue, and disable the offending topic at the source (toggle `stt-worker` `min_instances=0` and `max_instances=0` temporarily).
- DLQ keeps filling faster than you can drain → flip `STT_PROVIDER` (or `LLM_PROVIDER`) env var to `mock` to stop the bleed, then triage offline.
