import { test, expect } from "@playwright/test";

// Happy path: upload a tiny WAV, watch the status page progress to DONE.
// Requires the full docker-compose stack (Phase 4) to be running.

test("audio upload reaches DONE", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Transcribe & summarize/ })).toBeVisible();

  const fileInput = page.locator('input[type="file"]');
  // Smallest valid WAV payload (44-byte header + 2 silent samples).
  const wavHeader = Buffer.from([
    0x52, 0x49, 0x46, 0x46, 0x24, 0x00, 0x00, 0x00, 0x57, 0x41, 0x56, 0x45,
    0x66, 0x6d, 0x74, 0x20, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
    0x44, 0xac, 0x00, 0x00, 0x88, 0x58, 0x01, 0x00, 0x02, 0x00, 0x10, 0x00,
    0x64, 0x61, 0x74, 0x61, 0x00, 0x00, 0x00, 0x00,
  ]);
  await fileInput.setInputFiles({ name: "tiny.wav", mimeType: "audio/wav", buffer: wavHeader });

  await page.getByRole("button", { name: /Process audio/ }).click();
  await page.waitForURL(/\/tasks\/[0-9a-f-]+$/);

  // Status badge flips to "Done" when the pipeline finishes.
  await expect(page.getByText("Done", { exact: true })).toBeVisible({ timeout: 60_000 });
  // Summary panel appears once the LLM stage writes its row.
  await expect(page.getByRole("heading", { name: /Summary/ }).or(page.getByText("Summary", { exact: true }))).toBeVisible();
});
