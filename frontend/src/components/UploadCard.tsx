"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiClientError, api, uploadToSignedUrl } from "@/lib/api";
import { sha256OfFile } from "@/lib/sha256";

const ACCEPT = "audio/mpeg,audio/mp4,audio/wav,audio/webm,audio/ogg,audio/flac";
const MAX_BYTES = 500 * 1024 * 1024;

type Phase = "idle" | "hashing" | "creating" | "uploading" | "completing" | "done" | "error";

export function UploadCard() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);

  const onSubmit = useCallback(async () => {
    if (!file) return;
    setError(null);

    if (file.size > MAX_BYTES) {
      setError(`File too large (max ${MAX_BYTES / 1024 / 1024} MB).`);
      return;
    }

    try {
      setPhase("hashing");
      const sha = await sha256OfFile(file);

      setPhase("creating");
      const created = await api.createTask({
        filename: file.name,
        content_type: file.type || "audio/mpeg",
        audio_sha256: sha,
        audio_bytes: file.size,
      });

      setPhase("uploading");
      await uploadToSignedUrl(created.upload_url, created.upload_headers, file);

      setPhase("completing");
      await api.completeUpload(created.task_id);

      setPhase("done");
      router.push(`/tasks/${created.task_id}`);
    } catch (e) {
      setPhase("error");
      if (e instanceof ApiClientError) setError(`${e.status}: ${e.message}`);
      else if (e instanceof Error) setError(e.message);
      else setError("unknown error");
    }
  }, [file, router]);

  const busy = phase !== "idle" && phase !== "error" && phase !== "done";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Upload audio</h2>
      <p className="mt-1 text-sm text-slate-500">
        Audio is uploaded directly to object storage — it never passes through our API.
      </p>

      <label className="mt-5 block">
        <span className="sr-only">Choose audio file</span>
        <input
          type="file"
          accept={ACCEPT}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={busy}
          className="block w-full cursor-pointer rounded-lg border border-dashed border-slate-300 p-3 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-brand file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-fg hover:border-brand"
        />
      </label>

      {file && (
        <p className="mt-2 text-xs text-slate-500">
          {file.name} — {(file.size / 1024 / 1024).toFixed(2)} MB
        </p>
      )}

      <button
        onClick={onSubmit}
        disabled={!file || busy}
        className="mt-5 inline-flex w-full items-center justify-center rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {phaseLabel(phase)}
      </button>

      {error && (
        <p className="mt-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>
      )}
    </div>
  );
}

function phaseLabel(p: Phase): string {
  switch (p) {
    case "idle":       return "Process audio";
    case "hashing":    return "Hashing…";
    case "creating":   return "Reserving upload URL…";
    case "uploading":  return "Uploading to storage…";
    case "completing": return "Finalizing…";
    case "done":       return "Redirecting…";
    case "error":      return "Try again";
  }
}
