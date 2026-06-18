import type {
  ApiError,
  CreateTaskRequest,
  CreateTaskResponse,
  TaskResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";

export class ApiClientError extends Error {
  constructor(public readonly status: number, public readonly body: ApiError | { detail?: string } | null, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let body: ApiError | { detail?: string } | null = null;
    try {
      body = (await res.json()) as ApiError | { detail?: string };
    } catch {
      // non-json body
    }
    const message =
      (body && "error" in body && body.error?.message) ||
      (body && "detail" in body && body.detail) ||
      `HTTP ${res.status}`;
    throw new ApiClientError(res.status, body, message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  createTask: (body: CreateTaskRequest) =>
    request<CreateTaskResponse>("/v1/tasks", { method: "POST", body: JSON.stringify(body) }),

  completeUpload: (taskId: string) =>
    request<TaskResponse>(`/v1/tasks/${taskId}/complete`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  getTask: (taskId: string) => request<TaskResponse>(`/v1/tasks/${taskId}`),
};

/** Send the file to GCS via the gateway-issued URL. In prod this is a signed
 * PUT; in dev (fake-gcs-server) it's a POST to the JSON upload endpoint. The
 * server controls method/headers — the client just relays them. */
export async function uploadToSignedUrl(
  url: string,
  method: "PUT" | "POST",
  headers: Record<string, string>,
  file: File,
): Promise<void> {
  const res = await fetch(url, { method, headers, body: file });
  if (!res.ok) {
    throw new Error(`upload failed: ${res.status} ${await res.text()}`);
  }
}
