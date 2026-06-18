# Runbook — secret rotation

**When to use.** Scheduled quarterly rotation, or a credential is known/suspected leaked.

## Decision

If **leaked**: rotate now, even if a deploy is mid-flight. The risk of an active credential outweighs a botched canary.

If **scheduled**: pick a window where the on-call is awake and traffic is low.

Secrets we rotate:

| Secret | Owner | Frequency |
|---|---|---|
| `DATABASE_URL` (Cloud SQL `ai_stt_app` user password) | platform | quarterly |
| `OPENAI_API_KEY` | platform | quarterly; immediately if leaked |
| Cloud SQL `postgres` superuser | platform | manual, off-band |
| GitHub OIDC deployer SA | self-rotating, no action needed | — |

## Steps — `DATABASE_URL`

Expand-then-contract: create a new password without revoking the old one, switch services, then revoke.

```bash
PROJECT=ai-stt-prod
INSTANCE=ai-stt-prod-asia-east1
USER=ai_stt_app

# 1. Generate a new password.
NEW_PW=$(openssl rand -base64 36 | tr -d '/+=' | head -c 36)

# 2. Set it on the Cloud SQL user. (Cloud SQL keeps only one password per user
#    — so we do the brief swap, then update Secret Manager, then restart all
#    services. Tolerable because services hold pooled connections through the
#    swap window.)
gcloud sql users set-password "$USER" \
  --project="$PROJECT" --instance="$INSTANCE" \
  --password="$NEW_PW" --quiet

# 3. Build the new connection string and store a new secret version.
HOST=$(gcloud sql instances describe "$INSTANCE" --project="$PROJECT" \
       --format='value(ipAddresses[0].ipAddress)')
printf 'postgresql+asyncpg://%s:%s@%s:5432/ai_stt' "$USER" "$NEW_PW" "$HOST" \
  | gcloud secrets versions add DATABASE_URL --project="$PROJECT" --data-file=-

# 4. Force every service onto the new secret version.
for svc in ai-stt-api ai-stt-stt-worker ai-stt-llm-worker ai-stt-outbox; do
  for REGION in asia-east1 us-central1; do
    gcloud run services update "$svc" \
      --project="$PROJECT" --region="$REGION" \
      --update-secrets=DATABASE_URL=DATABASE_URL:latest --quiet 2>/dev/null || true
  done
done

# 5. After 1 hour with no errors, disable older secret versions.
gcloud secrets versions list DATABASE_URL --project="$PROJECT" --filter='state=ENABLED' \
  --format='value(name)' | tail -n +2 | while read -r v; do
    gcloud secrets versions disable "$v" --secret=DATABASE_URL --project="$PROJECT" --quiet
done
```

## Steps — `OPENAI_API_KEY`

```bash
PROJECT=ai-stt-prod

# 1. Create a new key in the OpenAI dashboard (keep the old key active).
# 2. Store it.
read -rsp "Paste new key: " NEW_KEY; echo
printf '%s' "$NEW_KEY" | gcloud secrets versions add OPENAI_API_KEY --project="$PROJECT" --data-file=-

# 3. Restart services that load it.
for svc in ai-stt-stt-worker ai-stt-llm-worker; do
  for REGION in asia-east1 us-central1; do
    gcloud run services update "$svc" \
      --project="$PROJECT" --region="$REGION" \
      --update-secrets=OPENAI_API_KEY=OPENAI_API_KEY:latest --quiet 2>/dev/null || true
  done
done

# 4. After 30 min with no errors, revoke the OLD key in the OpenAI dashboard
#    and disable the older Secret Manager version.
```

## Verify

- `gcloud sql users list --instance=...` shows the same user (no new one created by accident).
- Synthetic task end-to-end via the upload page reaches `DONE`.
- Provider error rate (`provider.errors`) flat at zero for 30 min after the swap.

## If this runbook itself fails

- `set-password` fails → the user might not exist. List with `gcloud sql users list` and recreate via Terraform.
- Services boot loop with "auth failed" → the secret got an old version pinned. Update the service to `--update-secrets=DATABASE_URL=DATABASE_URL:latest`. If still failing, **roll back** the secret version (`gcloud secrets versions disable <new>`) and investigate.
- OpenAI key valid in dashboard but services 401 → confirm the key copy didn't include trailing whitespace; redo step 2.
