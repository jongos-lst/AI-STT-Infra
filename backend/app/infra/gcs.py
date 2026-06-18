"""GCS helpers: signed URLs for upload, read stream for workers.

Signed URLs are issued by the API gateway only. Workers stream blobs directly,
authenticated via Workload Identity.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from urllib.parse import urlparse

from google.cloud import storage

from app.core.config import settings


def _client() -> storage.Client:
    return storage.Client(project=settings.gcp_project_id)


def signed_upload_url(bucket: str, object_path: str, *, content_type: str, content_length: int, ttl_seconds: int | None = None) -> str:
    """V4 signed URL bound to content type + length. Caller (browser) PUTs here."""
    ttl = ttl_seconds or settings.signed_url_ttl_seconds
    bucket_obj = _client().bucket(bucket)
    blob = bucket_obj.blob(object_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=ttl),
        method="PUT",
        content_type=content_type,
        headers={"X-Goog-Content-Length-Range": f"0,{content_length}"},
    )


def signed_download_url(bucket: str, object_path: str, *, ttl_seconds: int = 3600) -> str:
    blob = _client().bucket(bucket).blob(object_path)
    return blob.generate_signed_url(version="v4", expiration=timedelta(seconds=ttl_seconds), method="GET")


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    p = urlparse(uri)
    if p.scheme != "gs":
        raise ValueError(f"not a gs:// URI: {uri}")
    return p.netloc, p.path.lstrip("/")


@asynccontextmanager
async def open_for_read(audio_uri: str) -> AsyncIterator[bytes]:
    """Workers use this to stream audio to providers. Blocking under the hood;
    workers run one request at a time so it's fine."""
    bucket, path = parse_gcs_uri(audio_uri)
    blob = _client().bucket(bucket).blob(path)
    data = blob.download_as_bytes()
    yield data


def put_transcript_json(task_id: str, payload: dict) -> str:
    """Write transcript JSON to the transcripts bucket, return gs:// URI."""
    import json as _json
    bucket = _client().bucket(settings.gcs_bucket_transcripts)
    blob = bucket.blob(f"{task_id}/transcript.json")
    blob.upload_from_string(_json.dumps(payload), content_type="application/json")
    return f"gs://{settings.gcs_bucket_transcripts}/{task_id}/transcript.json"
