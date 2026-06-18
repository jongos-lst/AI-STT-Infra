#!/usr/bin/env bash
# Wrapper: `./infra/scripts/tf.sh <path-under-infra> <terraform-args...>`
# Runs the hashicorp/terraform image with the repo mounted; no host install.
set -euo pipefail
SUBPATH="${1:?usage: tf.sh <path-under-infra> <terraform args...>}"; shift
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
docker run --rm \
  -v "$ROOT:/work" \
  -w "/work/infra/$SUBPATH" \
  -e TF_IN_AUTOMATION=1 \
  hashicorp/terraform:1.10 "$@"
