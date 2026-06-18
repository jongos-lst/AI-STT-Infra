# Runbook — rollback a bad deploy

**When to use.** A deploy reached prod and you need to revert. The canary watcher auto-rolls back; this runbook covers the cases it didn't catch (slow regression, data corruption pattern only visible after promote, etc.).

## Decision

Three flavors:

- **Code-only regression** — flip Cloud Run traffic back to the previous revision. Fast, safe, no DB action.
- **Code + forward migration** — code rollback alone won't work; revert the migration too. Higher risk; do this only if the migration is **safely reversible** (renames, additive columns) — and never if it dropped a column.
- **Bad data written** — code rollback PLUS data fix. Open a separate incident channel; this runbook covers the code part.

If you're unsure which: rollback code first (it's cheap), watch the metrics, then decide.

## Steps — code-only rollback (Cloud Run traffic)

```bash
PROJECT=ai-stt-prod
REGIONS=("asia-east1" "us-central1")
SERVICES=(ai-stt-api ai-stt-stt-worker ai-stt-llm-worker ai-stt-outbox ai-stt-frontend)

for REGION in "${REGIONS[@]}"; do
  for SVC in "${SERVICES[@]}"; do
    PREV=$(gcloud run revisions list \
      --service="$SVC" --project="$PROJECT" --region="$REGION" \
      --format='value(metadata.name)' --limit=2 | tail -1)
    if [ -n "$PREV" ]; then
      echo ">>> $REGION/$SVC -> $PREV"
      gcloud run services update-traffic "$SVC" \
        --project="$PROJECT" --region="$REGION" \
        --to-revisions="$PREV=100" --quiet
    fi
  done
done
```

This swaps traffic in ~30 seconds per service. Run all in parallel if you're racing the incident.

## Steps — code + migration rollback

Only if the migration that shipped with the bad code is **reversible** (no destructive change). Expand-then-contract migrations are designed for this.

```bash
PROJECT=ai-stt-prod
PREV_TAG=<sha-of-previous-working-image>  # find it on the Artifact Registry page

# 1. Code rollback (see steps above), reaching the revision tagged $PREV_TAG.
# 2. Then downgrade the schema via a one-shot Cloud Run Job.
gcloud run jobs deploy ai-stt-migrate-down \
  --project="$PROJECT" --region=asia-east1 \
  --image="asia-east1-docker.pkg.dev/ai-stt-shared/ai-stt/api:$PREV_TAG" \
  --command=alembic --args=downgrade,-1 \
  --service-account=ai-stt-stt-worker@$PROJECT.iam.gserviceaccount.com \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest \
  --vpc-connector=ai-stt-prod-conn-asia-east1 \
  --vpc-egress=private-ranges-only --quiet

gcloud run jobs execute ai-stt-migrate-down \
  --project="$PROJECT" --region=asia-east1 --wait --quiet
```

If the migration was destructive (column drop, table drop), **do not** run `downgrade`. Restore from PITR instead — that's a separate, slower runbook; page the DBA on-call.

## Verify

- API 5xx returns to baseline within 5 minutes.
- Outbox lag drops back to the normal range (a few seconds).
- A synthetic upload reaches `DONE`.
- Cloud Run revision list (`gcloud run revisions list`) shows the previous revision serving 100% traffic.

## After

- Tag the bad image in Artifact Registry with `bad/<incident-id>` so it can't be accidentally redeployed.
- Open a postmortem under `docs/incidents/`.
- File the regression as a release-blocking issue; do not deploy a fix until it's been replayed against staging and survived a 30-min soak.

## If this runbook itself fails

- `update-traffic` fails with "revision not found" → the previous revision was already garbage-collected (Cloud Run keeps 1000). Redeploy from the previous Artifact Registry tag instead (see CI workflow `deploy-prod.yml`).
- Both regions are bad and there's no previous revision in either → rebuild from `git checkout <last-good-tag>` and ship a hotfix via the standard CI path. Communicate that recovery will take ~10–15 min.
