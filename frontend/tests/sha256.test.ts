import { describe, expect, it } from "vitest";
import { sha256OfFile } from "@/lib/sha256";

describe("sha256OfFile", () => {
  it("matches known vector for 'hello'", async () => {
    const file = new File(["hello"], "x.txt", { type: "text/plain" });
    const hex = await sha256OfFile(file);
    expect(hex).toBe("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");
  });

  it("returns 64-char lowercase hex", async () => {
    const file = new File([new Uint8Array(1024)], "z.bin");
    const hex = await sha256OfFile(file);
    expect(hex).toMatch(/^[0-9a-f]{64}$/);
  });
});
