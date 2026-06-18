import { describe, expect, it } from "vitest";
import { PROGRESS_PERCENT, STATUS_LABEL, STATUS_TONE } from "@/lib/status";
import { TERMINAL_STATUSES } from "@/lib/types";

const ALL = [
  "PENDING_UPLOAD", "QUEUED", "STT_RUNNING", "STT_DONE", "LLM_RUNNING", "DONE", "FAILED",
] as const;

describe("status tables", () => {
  it("cover every status", () => {
    for (const s of ALL) {
      expect(STATUS_LABEL[s]).toBeTruthy();
      expect(STATUS_TONE[s]).toBeTruthy();
      expect(PROGRESS_PERCENT[s]).toBeGreaterThan(0);
    }
  });

  it("monotonically progress until terminal", () => {
    const ordered = ALL.filter((s) => !TERMINAL_STATUSES.has(s));
    for (let i = 1; i < ordered.length; i++) {
      expect(PROGRESS_PERCENT[ordered[i]]).toBeGreaterThan(PROGRESS_PERCENT[ordered[i - 1]]);
    }
  });
});
