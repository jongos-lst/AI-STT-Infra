# CI/CD

| Workflow | Triggers | What it does |
|---|---|---|
| `backend-ci.yml`  | PR / push to `backend/**` | ruff + mypy + pytest unit (against Postgres + Redis services) + coverage artifact |
| `frontend-ci.yml` | PR / push to `frontend/**` | typecheck + vitest + production `next build` |
| `infra-ci.yml`    | PR / push to `infra/**` | `terraform fmt -check`, `validate` on all 3 envs; on PR, runs `plan` against staging and comments the diff |
| `security.yml`    | PR / push + daily 04:17 UTC cron | gitleaks, pip-audit, npm audit, trivy filesystem scan → SARIF to Code Scanning |
| `build.yml`       | push to `main` / `v*` tag (or called) | matrix build for `api` + `frontend` → push to Artifact Registry, Trivy image scan, **cosign keyless sign**, provenance + SBOM attestations |
| `deploy-staging.yml` | push to `main` | calls `build.yml`, `terraform apply envs/staging`, runs Alembic via Cloud Run Job, deploys revisions, triggers `e2e.yml` against the staging URL |
| `e2e.yml`         | called / manual | Playwright against the supplied `base_url`; uploads the report |
| `deploy-prod.yml` | `v*` tag (or manual) | build → **manual approval gate** (`prod-gate` env) → `terraform apply envs/prod` → migrate → **canary 10%** in both regions → 10-min SLO watch → promote 100% or auto-rollback |

## Required GitHub configuration

### Secrets
None — all auth is OIDC. No long-lived keys ever.

### Repo variables
Set under `Settings → Secrets and variables → Actions → Variables`:

| Variable | Source | Example |
|---|---|---|
| `GCP_WIF_PROVIDER`           | bootstrap output `github_actions_inputs.workload_identity_provider` | `projects/123/locations/global/workloadIdentityPools/github-actions/providers/github` |
| `GCP_DEPLOYER_SA`            | bootstrap output `.service_account`                                  | `gha-deployer@ai-stt-shared.iam.gserviceaccount.com` |
| `ARTIFACT_REPO`              | bootstrap output `artifact_repo`                                     | `asia-east1-docker.pkg.dev/ai-stt-shared/ai-stt` |
| `ARTIFACT_REGION`            | first segment of `ARTIFACT_REPO`                                     | `asia-east1` |
| `GCP_PROJECT_ID_STAGING`     | staging GCP project                                                  | `ai-stt-staging` |
| `GCP_PROJECT_ID_PROD`        | prod GCP project                                                     | `ai-stt-prod` |
| `STAGING_REGION`             | staging primary region                                               | `asia-east1` |
| `PRIMARY_REGION`             | prod primary region                                                  | `asia-east1` |
| `STAGING_HOST`               | public hostname for staging                                          | `stg.ai-stt.example.com` |
| `PROD_HOST`                  | public hostname for prod                                             | `ai-stt.example.com` |
| `STAGING_BASE_URL`           | URL for Playwright to hit                                            | `https://stg.ai-stt.example.com` |
| `NOTIFICATION_EMAIL`         | for alert policies                                                   | `oncall@example.com` |

### Environments
Create two GitHub Environments (`Settings → Environments`):

- **`staging`** — no protection rules required
- **`prod-gate`** — *required reviewers* = your team. This is what makes prod a true manual gate.
- **`prod`** — no protection rules; relies on `prod-gate` upstream

## OIDC

Workflows authenticate via `google-github-actions/auth@v2` using the WIF pool created by `infra/envs/bootstrap`. The pool is gated by `attribute.repository == "jongos-lst/AI-STT-Infra"`, so forks cannot mint tokens.

## Rollback

Automatic during canary if 5xx count exceeds threshold in the 10-min watch window. To roll back manually after promote:

```bash
for svc in ai-stt-api ai-stt-stt-worker ai-stt-llm-worker ai-stt-outbox ai-stt-frontend; do
  PREV=$(gcloud run revisions list --service="$svc" --region=asia-east1 --format='value(metadata.name)' --limit=2 | tail -1)
  gcloud run services update-traffic "$svc" --region=asia-east1 --to-revisions="$PREV=100"
done
```
