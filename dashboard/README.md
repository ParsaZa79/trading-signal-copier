# Trading Dashboard (Next.js)

Frontend UI for monitoring account performance, open positions, orders, trade history, and bot status/control.

## Requirements

- Node.js 20.19+
- Bun 1.3+
- Running backend API (`api/`) on port `8000` by default

## Setup

```bash
cd dashboard
bun install --frozen-lockfile
```

## Run (Development)

```bash
cd dashboard
bun run dev
```

Open `http://localhost:3000`.

## Environment

Configure `dashboard/.env.local` as needed:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
DASHBOARD_PROXY_SECRET=
NEXT_PUBLIC_STRATEGY_LAB_ENABLED=false
BETTER_AUTH_ENABLED=false
STRATEGY_LAB_ENABLED=false
OPEN_SIGNUP_ENABLED=false
```

If omitted, these defaults are used by `src/lib/constants.ts`.
If `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set, the dashboard uses Clerk sign-in/sign-up
pages and route protection. The dashboard server needs `CLERK_SECRET_KEY`, and the
dashboard plus API must share the same `DASHBOARD_PROXY_SECRET`.

### Better Auth foundation

Better Auth is installed alongside Clerk but is disabled by default. Clerk remains the
active provider and continues to control protected routes. The `/api/auth/*` handler
continues to use the existing Clerk-to-FastAPI proxy unless both
`BETTER_AUTH_ENABLED=true` and `STRATEGY_LAB_ENABLED=true` are set on the dashboard
server.

Before enabling the handler, configure the server-only values documented in
`.env.example`: a generated `BETTER_AUTH_SECRET`, a dedicated node-postgres
`BETTER_AUTH_DATABASE_URL`, the dashboard origin in `BETTER_AUTH_URL`, the FastAPI
origin in `BETTER_AUTH_JWT_AUDIENCE`, and authenticated SMTP settings. The PostgreSQL
connection uses the separate `auth` schema; create that schema and apply the Better
Auth core, Admin, JWT/JWKS, and database rate-limit schema before activation. Schema
provisioning is a prerequisite and is not performed by this foundation task; with the
complete activation environment, the pinned CLI can discover `src/lib/auth.ts`:

```bash
BETTER_AUTH_CLI=true bunx auth@1.6.23 generate \
  --config ./src/lib/auth.ts \
  --output ./better-auth-schema.sql
```

Before activation, also verify the Traefik client-IP header/trusted-proxy chain so
database-backed per-IP auth limits cannot collapse unrelated users into one fallback
rate-limit bucket.

`TURNSTILE_SECRET_KEY` is required before Better Auth can be activated, protecting its
email sign-in, signup, and password-reset endpoints. `OPEN_SIGNUP_ENABLED` still
defaults to `false`; keep it disabled until the release gates and the later auth cutover
tasks are complete. Secrets and SMTP credentials belong in runtime/Dokploy secrets,
never in committed env files or Docker build arguments.

## Available Scripts

- `bun run dev` — Start dev server
- `bun run build` — Build production bundle
- `bun run start` — Run production server
- `bun run lint` — Run ESLint
- `bun run test` — Run the Vitest suite

## API Integration

The dashboard expects:

- REST endpoints under `/api/*` on the backend
- WebSocket streams at `/ws` and `/ws/logs`

Ensure the API service is running before using data-driven pages.
