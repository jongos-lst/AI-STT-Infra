import { describe, expect, it } from "vitest";
import { buildCsp } from "@/lib/csp";

const PROD = { mode: "prod" as const, apiBaseUrl: "https://api.example.com" };
const DEV = {
  mode: "dev" as const,
  apiBaseUrl: "http://localhost:8080",
  gcsBaseUrl: "http://localhost:4443",
};

describe("buildCsp", () => {
  it("defaults to same-origin and blocks framing + plugins", () => {
    const csp = buildCsp(PROD);
    expect(csp).toMatch(/default-src 'self'/);
    expect(csp).toMatch(/frame-ancestors 'none'/);
    expect(csp).toMatch(/object-src 'none'/);
    expect(csp).toMatch(/base-uri 'self'/);
    expect(csp).toMatch(/form-action 'self'/);
  });

  it("allows the configured API origin in connect-src", () => {
    expect(buildCsp(PROD)).toMatch(
      /connect-src 'self' https:\/\/api\.example\.com/,
    );
  });

  it("includes dev GCS origin when provided", () => {
    const csp = buildCsp(DEV);
    expect(csp).toContain("http://localhost:8080");
    expect(csp).toContain("http://localhost:4443");
  });

  it("auto-allows real GCS in prod for direct uploads", () => {
    expect(buildCsp(PROD)).toContain("https://storage.googleapis.com");
  });

  it("permits unsafe-eval only in dev (React Refresh)", () => {
    expect(buildCsp(DEV)).toMatch(/'unsafe-eval'/);
    expect(buildCsp(PROD)).not.toMatch(/'unsafe-eval'/);
  });

  it("upgrades insecure requests only in prod", () => {
    expect(buildCsp(PROD)).toMatch(/upgrade-insecure-requests/);
    expect(buildCsp(DEV)).not.toMatch(/upgrade-insecure-requests/);
  });

  it("survives a malformed apiBaseUrl by preserving the literal", () => {
    const csp = buildCsp({ mode: "prod", apiBaseUrl: "not-a-url" });
    // Should not throw; the literal goes through to connect-src.
    expect(csp).toContain("not-a-url");
  });

  it("emits a single line that is parseable as directives", () => {
    const csp = buildCsp(PROD);
    expect(csp.split(";").length).toBeGreaterThan(5);
    expect(csp).not.toContain("\n");
  });
});
