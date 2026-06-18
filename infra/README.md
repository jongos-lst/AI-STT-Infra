# infra/ — GCP infrastructure

Terraform 1.10+. State lives in a per-env GCS bucket (configured in `envs/*/backend.tf`).

## Layout

```
modules/
  network/             VPC + subnets + serverless VPC connector
  cloud-sql/           Postgres 16 HA + PITR + private IP
  pubsub/              topics + push subs (OIDC-auth'd) + DLQ
  gcs/                 buckets with lifecycle, CMEK-ready, IAM
  secret-manager/      app secrets + accessor bindings
  artifact-registry/   docker repo
  service-accounts/    least-privilege SAs per workload
  cloud-run/           service module (callable per region)
  edge/                Global HTTPS LB + Cloud Armor + Cloud CDN
  observability/       log sinks, custom metrics, SLO alerts
  github-oidc/         Workload Identity Federation for GitHub Actions

envs/
  staging/             single region (asia-east1), small sizes
  prod/                multi-region (asia-east1 + us-central1) active-active
  bootstrap/           one-shot: state bucket + WIF pool (chicken-and-egg)
```

## First-time bootstrap

```bash
cd infra/envs/bootstrap
terraform init
terraform apply -var="project_id=<PROJECT>" -var="github_owner=jongos-lst" -var="github_repo=AI-STT-Infra"
```

This provisions:
- The GCS bucket used as remote state for staging + prod
- Artifact Registry
- Workload Identity pool for GitHub Actions OIDC
- A `gha-deployer` service account bound to it (no JSON keys ever)

## Per-env deploy

```bash
cd infra/envs/staging
cp terraform.tfvars.example terraform.tfvars   # fill in project_id
terraform init
terraform plan
terraform apply
```

Same for `prod/`. CI does this for you on merge.

## Local validation (no host install required)

```bash
# from the repo root
./infra/scripts/tf.sh envs/staging fmt -recursive
./infra/scripts/tf.sh envs/staging validate
```

`tf.sh` is a thin wrapper around `docker run hashicorp/terraform`.
