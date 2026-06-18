# frontend

Next.js 15 (App Router, TypeScript). Upload page → signed-URL PUT directly to GCS → poll task status → render summary.

```bash
cp .env.example .env.local
npm install
npm run dev
```

The frontend talks only to the FastAPI gateway. Audio bytes never traverse the API — the browser PUTs straight to GCS using a signed URL the gateway issues.

## Test

```bash
npm test            # vitest unit
npm run test:e2e    # playwright (needs full stack via docker-compose)
npm run typecheck
```
