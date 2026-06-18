#!/usr/bin/env bash
# Create the two buckets in fake-gcs-server. Idempotent.
set -euo pipefail

: "${GCS_HOST:=http://gcs:4443}"
: "${GCS_BUCKET_AUDIO:=ai-stt-dev-audio}"
: "${GCS_BUCKET_TRANSCRIPTS:=ai-stt-dev-transcripts}"

echo "[init-gcs] waiting for fake-gcs-server at $GCS_HOST"
for i in $(seq 1 30); do
  if curl -fsS "$GCS_HOST/storage/v1/b?project=ai-stt-dev" >/dev/null 2>&1; then break; fi
  sleep 1
done

create_bucket() {
  local name="$1"
  # Create with a CORS rule that allows the frontend dev origin. Includes
  # X-Goog-Content-Length-Range so the browser PUT (which mirrors the signed
  # URL contract) is not pre-flight rejected.
  curl -fsS -X POST "$GCS_HOST/storage/v1/b?project=ai-stt-dev" \
    -H 'Content-Type: application/json' \
    -d "{
      \"name\":\"${name}\",
      \"cors\":[{
        \"origin\":[\"http://localhost:3000\",\"http://localhost:8080\"],
        \"method\":[\"GET\",\"PUT\",\"POST\",\"HEAD\",\"OPTIONS\"],
        \"responseHeader\":[\"Content-Type\",\"X-Goog-Content-Length-Range\",\"X-Goog-Resumable\",\"Authorization\"],
        \"maxAgeSeconds\":3600
      }]
    }" >/dev/null \
    && echo "[init-gcs] bucket ${name}: created (cors set)" \
    || echo "[init-gcs] bucket ${name}: already exists (ok)"
}

create_bucket "$GCS_BUCKET_AUDIO"
create_bucket "$GCS_BUCKET_TRANSCRIPTS"

echo "[init-gcs] done"
