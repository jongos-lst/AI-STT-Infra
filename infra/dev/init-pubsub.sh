#!/usr/bin/env bash
# Creates topics, push subscriptions targeting the workers, and a DLQ on the
# local Pub/Sub emulator. Idempotent — safe to re-run.
set -euo pipefail

: "${PUBSUB_EMULATOR_HOST:=pubsub-emulator:8085}"
: "${GCP_PROJECT_ID:=ai-stt-dev}"
: "${PUBSUB_TOPIC_STT:=stt.requested}"
: "${PUBSUB_TOPIC_LLM:=llm.requested}"
: "${PUBSUB_TOPIC_DLQ:=tasks.dlq}"
: "${STT_PUSH_ENDPOINT:=http://stt-worker:8080/_pubsub/stt}"
: "${LLM_PUSH_ENDPOINT:=http://llm-worker:8080/_pubsub/llm}"

API="http://${PUBSUB_EMULATOR_HOST}"

echo "[init-pubsub] waiting for emulator at $API"
for i in $(seq 1 30); do
  if curl -fsS "$API" >/dev/null 2>&1; then break; fi
  sleep 1
done

put_topic() {
  local name="$1"
  curl -fsS -X PUT "$API/v1/projects/${GCP_PROJECT_ID}/topics/${name}" \
    -H 'Content-Type: application/json' -d '{}' >/dev/null \
    && echo "[init-pubsub] topic ${name}: created" \
    || echo "[init-pubsub] topic ${name}: already exists (ok)"
}

put_push_sub() {
  local sub="$1" topic="$2" endpoint="$3"
  local body
  body=$(printf '{"topic":"projects/%s/topics/%s","pushConfig":{"pushEndpoint":"%s"},"ackDeadlineSeconds":60,"deadLetterPolicy":{"deadLetterTopic":"projects/%s/topics/%s","maxDeliveryAttempts":5}}' \
    "$GCP_PROJECT_ID" "$topic" "$endpoint" "$GCP_PROJECT_ID" "$PUBSUB_TOPIC_DLQ")
  curl -fsS -X PUT "$API/v1/projects/${GCP_PROJECT_ID}/subscriptions/${sub}" \
    -H 'Content-Type: application/json' -d "$body" >/dev/null \
    && echo "[init-pubsub] sub ${sub}: created → ${endpoint}" \
    || echo "[init-pubsub] sub ${sub}: already exists (ok)"
}

put_topic "$PUBSUB_TOPIC_DLQ"
put_topic "$PUBSUB_TOPIC_STT"
put_topic "$PUBSUB_TOPIC_LLM"

put_push_sub "stt-worker"    "$PUBSUB_TOPIC_STT" "$STT_PUSH_ENDPOINT"
put_push_sub "llm-worker"    "$PUBSUB_TOPIC_LLM" "$LLM_PUSH_ENDPOINT"
# pull-style subscription on DLQ so an operator can inspect failures.
curl -fsS -X PUT "$API/v1/projects/${GCP_PROJECT_ID}/subscriptions/dlq-inspector" \
  -H 'Content-Type: application/json' \
  -d "$(printf '{"topic":"projects/%s/topics/%s","ackDeadlineSeconds":60}' "$GCP_PROJECT_ID" "$PUBSUB_TOPIC_DLQ")" \
  >/dev/null && echo "[init-pubsub] sub dlq-inspector: created" \
  || echo "[init-pubsub] sub dlq-inspector: already exists (ok)"

echo "[init-pubsub] done"
