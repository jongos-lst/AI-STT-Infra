# Runbook — region failover

**When to use.** One Cloud Run region is failing health checks (red on the dashboard, 5xx alert firing only on that region's services) and isn't recovering on its own within 10 minutes.

## Decision

Skip this runbook if the **whole** product is failing — that's not a region issue, escalate immediately.

If only one region is bad:

- **Soft failover (no DB changes).** Drain traffic out of the bad region via the load balancer. The other region absorbs it. Use this first.
- **Hard failover (write side, including DB).** Only if the primary Cloud SQL region is down — promote the read replica. Has data-loss risk if the primary recovers later.

Default to **soft** unless you're certain Cloud SQL is the failure.

## Steps — soft failover (drain a region)

The Global LB picks the nearest healthy backend automatically once a region's services fail health checks. To force it:

```bash
PROJECT=ai-stt-prod
BAD_REGION=us-central1   # the one to drain

# Take every service in the bad region out of LB rotation by scaling to zero.
for svc in ai-stt-api ai-stt-frontend; do
  gcloud run services update "$svc" \
    --project="$PROJECT" --region="$BAD_REGION" \
    --min-instances=0 --max-instances=0 --quiet
done
```

This stops new requests within ~30 s. Existing requests drain naturally.

Workers (`ai-stt-stt-worker`, `ai-stt-llm-worker`) consume from a **global** Pub/Sub topic — leave the surviving region's workers alone, they'll pick up the slack.

## Steps — hard failover (Cloud SQL)

**Only if the primary instance is verifiably down** (Cloud SQL console shows the primary as DOWN, automatic HA failover hasn't recovered within 10 min).

```bash
PROJECT=ai-stt-prod
REPLICA=ai-stt-prod-replica-us-central1   # promote this

# 1. Promote the replica to a standalone instance.
gcloud sql instances promote-replica "$REPLICA" --project="$PROJECT" --quiet

# 2. Update the DATABASE_URL secret to point at the new primary's private IP.
NEW_IP=$(gcloud sql instances describe "$REPLICA" --project="$PROJECT" --format='value(ipAddresses[0].ipAddress)')
USER=ai_stt_app
DB=ai_stt
# Re-use the password from the existing version — fetch it, repackage, version-add:
PW=$(gcloud secrets versions access latest --secret=DATABASE_URL --project="$PROJECT" | sed -E 's#.*://[^:]+:([^@]+)@.*#\1#')
printf 'postgresql+asyncpg://%s:%s@%s:5432/%s' "$USER" "$PW" "$NEW_IP" "$DB" \
  | gcloud secrets versions add DATABASE_URL --project="$PROJECT" --data-file=-

# 3. Force every service to pick up the new secret version.
for svc in ai-stt-api ai-stt-stt-worker ai-stt-llm-worker ai-stt-outbox; do
  for REGION in asia-east1 us-central1; do
    gcloud run services update "$svc" --project="$PROJECT" --region="$REGION" \
      --update-secrets=DATABASE_URL=DATABASE_URL:latest --quiet || true
  done
done
```

## Verify

- `gcloud monitoring time-series list` for the bad region's 5xx metric returns to zero.
- Synthetic check (Cloud Monitoring uptime check or `curl https://<host>/healthz` from outside) returns 200.
- Dashboard: backlog on `stt.requested` / `llm.requested` is draining, not growing.

## After the incident

- Re-set `min/max instances` on the drained region (Terraform variables, then `apply`).
- For a hard failover, rebuild the destroyed replica: `terraform apply` will recreate it from current state.
- Write a brief postmortem under `docs/incidents/YYYY-MM-DD-region.md`.

## If this runbook itself fails

- `update` returns `permission denied` → your account is missing `roles/run.admin` on the prod project.
- Replica promote fails → call GCP support (P1 incident in their console), don't keep retrying.
