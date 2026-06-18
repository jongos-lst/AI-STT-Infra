// Mirrors backend/app/api/schemas.py — keep in sync.

export type TaskStatus =
  | "PENDING_UPLOAD"
  | "QUEUED"
  | "STT_RUNNING"
  | "STT_DONE"
  | "LLM_RUNNING"
  | "DONE"
  | "FAILED";

export const TERMINAL_STATUSES: ReadonlySet<TaskStatus> = new Set(["DONE", "FAILED"]);

export interface CreateTaskRequest {
  filename: string;
  content_type: string;
  audio_sha256: string;
  audio_bytes: number;
}

export interface CreateTaskResponse {
  task_id: string;
  upload_url: string;
  upload_method: "PUT";
  upload_headers: Record<string, string>;
  expires_in_seconds: number;
}

export interface TaskResponse {
  task_id: string;
  status: TaskStatus;
  error?: string | null;
  transcript?: string | null;
  summary?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ApiError {
  error: { code: string; message: string };
}
