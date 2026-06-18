import { PROGRESS_PERCENT } from "@/lib/status";
import type { TaskStatus } from "@/lib/types";

export function ProgressBar({ status }: { status: TaskStatus }) {
  const pct = PROGRESS_PERCENT[status];
  const failed = status === "FAILED";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div
        className={`h-full transition-all duration-500 ${failed ? "bg-rose-500" : "bg-brand"}`}
        style={{ width: `${pct}%` }}
        aria-valuenow={pct}
        role="progressbar"
      />
    </div>
  );
}
