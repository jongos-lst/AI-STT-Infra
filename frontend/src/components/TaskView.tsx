"use client";

import { useEffect, useState } from "react";
import { ApiClientError, api } from "@/lib/api";
import { TERMINAL_STATUSES, type TaskResponse } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { ProgressBar } from "./ProgressBar";

export function TaskView({ taskId }: { taskId: string }) {
  const [task, setTask] = useState<TaskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const next = await api.getTask(taskId);
        if (cancelled) return;
        setTask(next);
        if (!TERMINAL_STATUSES.has(next.status)) {
          timer = setTimeout(tick, 1500);
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiClientError) setError(`${e.status}: ${e.message}`);
        else if (e instanceof Error) setError(e.message);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [taskId]);

  if (error) return <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>;
  if (!task) return <p className="text-sm text-slate-500">Loading…</p>;

  const filename = (task.metadata?.filename as string | undefined) ?? "audio";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wider text-slate-400">Task</p>
          <p className="font-mono text-sm text-slate-700">{task.task_id}</p>
        </div>
        <StatusBadge status={task.status} />
      </div>

      <div>
        <p className="text-sm text-slate-700">{filename}</p>
        <div className="mt-2">
          <ProgressBar status={task.status} />
        </div>
      </div>

      {task.error && (
        <div className="rounded-md bg-rose-50 p-3 text-sm text-rose-700">
          <strong>Failure:</strong> {task.error}
        </div>
      )}

      {task.transcript && (
        <details className="rounded-lg border border-slate-200 p-4" open>
          <summary className="cursor-pointer font-medium text-slate-900">Transcript</summary>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
            {task.transcript}
          </p>
        </details>
      )}

      {task.summary && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <p className="font-medium text-emerald-900">Summary</p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-emerald-900">
            {task.summary}
          </p>
        </div>
      )}
    </div>
  );
}
