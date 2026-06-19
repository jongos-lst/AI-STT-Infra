// Content-Security-Policy builder. Pure string logic so we can unit-test it
// without booting Next.js. Imported by `next.config.ts` at build time.
//
// Threat model: this CSP is the second line of defense for XSS. React already
// escapes everything by default and we have no `dangerouslySetInnerHTML`; CSP
// catches the cases where that breaks (a future component, a runtime-injected
// script, an exfil to a third-party origin).
//
// Upgrade path: replace `'unsafe-inline'` on script-src with per-request nonces
// via Next middleware. That's a separate change — the basic CSP earns its
// keep first.

export type CspMode = "dev" | "prod";

export interface CspOptions {
  mode: CspMode;
  /** API origin the browser is allowed to call (https://api.example.com). */
  apiBaseUrl: string;
  /** Object-storage origin for direct uploads. Optional. */
  gcsBaseUrl?: string;
}

export function buildCsp({ mode, apiBaseUrl, gcsBaseUrl }: CspOptions): string {
  const apiOrigin = originOf(apiBaseUrl);
  const gcsOrigin = gcsBaseUrl ? originOf(gcsBaseUrl) : null;

  const connectSrc = ["'self'", apiOrigin];
  if (gcsOrigin) connectSrc.push(gcsOrigin);
  if (mode === "prod") connectSrc.push("https://storage.googleapis.com");

  // Dev needs unsafe-eval for Next's React Refresh / sourcemaps.
  // Prod keeps unsafe-inline (RSC payloads, hydration) until we wire nonces.
  const scriptSrc =
    mode === "dev"
      ? ["'self'", "'unsafe-inline'", "'unsafe-eval'"]
      : ["'self'", "'unsafe-inline'"];

  // Tailwind ships precomputed styles + a few inline ones — unsafe-inline is
  // the pragmatic choice; a nonce-based pass can come later if needed.
  const styleSrc = ["'self'", "'unsafe-inline'"];

  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": scriptSrc,
    "style-src": styleSrc,
    "img-src": ["'self'", "data:", "https:"],
    "font-src": ["'self'", "data:"],
    "connect-src": connectSrc,
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
  };
  if (mode === "prod") directives["upgrade-insecure-requests"] = [];

  return Object.entries(directives)
    .map(([key, vals]) => (vals.length > 0 ? `${key} ${vals.join(" ")}` : key))
    .join("; ");
}

function originOf(url: string): string {
  try {
    const u = new URL(url);
    return `${u.protocol}//${u.host}`;
  } catch {
    // Fall back to the raw value so config doesn't break on a typo —
    // the CSP just won't match anything, which is the safe failure mode.
    return url;
  }
}
