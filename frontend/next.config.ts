import type { NextConfig } from "next";

import { buildCsp } from "./src/lib/csp";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";

// Mode is driven by the *application* env, not NODE_ENV. The standalone
// container ships with NODE_ENV=production even when we run it locally in
// docker-compose against the dev stack — we still want React Refresh-style
// allowances there.
const mode: "dev" | "prod" =
  process.env.NEXT_PUBLIC_APP_ENV === "prod" ? "prod" : "dev";

// Optional override: if the API issues upload URLs against a non-default
// origin (fake-gcs-server in dev, custom CDN, …), allow it in connect-src.
const gcsBaseUrl =
  process.env.NEXT_PUBLIC_GCS_BASE_URL ||
  (mode === "dev" ? "http://localhost:4443" : undefined);

const csp = buildCsp({ mode, apiBaseUrl, gcsBaseUrl });

const config: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    typedRoutes: true,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
        ],
      },
    ];
  },
};

export default config;
