import type { TaskStatus } from "./types";

export const STATUS_LABEL: Record<TaskStatus, string> = {
  PENDING_UPLOAD: "Waiting for upload",
  QUEUED: "Queued",
  STT_RUNNING: "Transcribing",
  STT_DONE: "Transcription done",
  LLM_RUNNING: "Summarizing",
  DONE: "Done",
  FAILED: "Failed",
};

export const STATUS_TONE: Record<TaskStatus, string> = {
  PENDING_UPLOAD: "bg-slate-100 text-slate-700",
  QUEUED:         "bg-blue-100 text-blue-700",
  STT_RUNNING:    "bg-amber-100 text-amber-800",
  STT_DONE:       "bg-amber-100 text-amber-800",
  LLM_RUNNING:    "bg-amber-100 text-amber-800",
  DONE:           "bg-emerald-100 text-emerald-700",
  FAILED:         "bg-rose-100 text-rose-700",
};

export const PROGRESS_PERCENT: Record<TaskStatus, number> = {
  PENDING_UPLOAD: 10,
  QUEUED: 25,
  STT_RUNNING: 45,
  STT_DONE: 60,
  LLM_RUNNING: 80,
  DONE: 100,
  FAILED: 100,
};
