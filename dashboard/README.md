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
connection uses the separate `auth` schema. Runtime activation requires both private
server variables `BETTER_AUTH_ENABLED=true` and `STRATEGY_LAB_ENABLED=true`; the
browser-visible `NEXT_PUBLIC_STRATEGY_LAB_ENABLED` flag never activates auth.

#### PostgreSQL auth-schema migrations

The committed workflow lives in `migrations/auth/` and `scripts/`. It deliberately
does not use `auth migrate`: Better Auth emits unqualified PostgreSQL DDL, and its
direct migration runner does not provide this repository's validation, transaction,
or checksum guarantees.

To generate a migration after changing Better Auth options or plugins:

```bash
# TEST_DATABASE_URL must be a disposable PostgreSQL database. Never use production.
TEST_DATABASE_URL=postgresql://... bun run auth:schema:apply:test
TEST_DATABASE_URL=postgresql://... bun run auth:schema:generate -- \
  migrations/auth/0002_descriptive_name.sql
bun run auth:schema:validate
TEST_DATABASE_URL=postgresql://... bun run test:postgres
```

`0000_create_auth_schema.sql` creates only the `auth` schema in a separate
transaction. Generation uses the pinned `better-auth` library and inspects the
disposable database after all committed migrations have been applied. The generator
rejects empty or unsafe SQL, rejects schema-qualified/generated transaction commands,
and wraps accepted unqualified DDL with `BEGIN` plus
`SET LOCAL search_path TO "auth", pg_catalog`. Review and commit the prepared file.

Apply reviewed migrations to a target only from a secret-bearing runtime shell:

```bash
BETTER_AUTH_DATABASE_URL=postgresql://... bun run auth:schema:apply
```

The apply command validates every file again, creates `auth` separately, and applies
each migration plus its SHA-256 ledger entry atomically under a PostgreSQL advisory
lock. Reapplication is a no-op; a changed checksum or any SQL error fails closed and
rolls back. Do not pass database URLs on the command line or commit them.

The optional PostgreSQL integration suite drops and recreates only the `auth` schema,
so it is skipped unless `TEST_DATABASE_URL` is set. It verifies schema placement and
real Better Auth role, verification, JWT/JWKS five-minute claim, one-use password
reset, and session-revocation behavior.

#### Trusted client IP prerequisite

Database-backed auth rate limits are safe only after the client-IP trust boundary is
verified. The dashboard origin must be reachable only through the intended Traefik
instance. Traefik must strip client-supplied `X-Forwarded-For`/`X-Real-IP` values and
write the authoritative client chain; the application network must trust only the
exact Traefik IP or narrow CIDR, never the public internet or a broad private range.
If the runtime is configured for a single-value forwarded header, Traefik must
overwrite it rather than append an untrusted value.

Before activation, prove that direct origin access is blocked, spoofed forwarding
headers are replaced, two distinct external clients produce distinct resolved client
addresses/rate-limit keys, and requests with no trustworthy address fail the readiness
checklist. Otherwise unrelated users can collapse into one shared per-path bucket, or
an attacker can evade limits by spoofing headers.

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
- `bun run test:postgres` — Run the opt-in disposable-PostgreSQL auth suite
- `bun run auth:schema:validate` — Validate committed auth migrations
- `bun run auth:schema:apply` — Transactionally apply auth migrations

## API Integration

The dashboard expects:

- REST endpoints under `/api/*` on the backend
- WebSocket streams at `/ws` and `/ws/logs`

Ensure the API service is running before using data-driven pages.
