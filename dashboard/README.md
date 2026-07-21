# Trading Dashboard (Next.js)

Frontend UI for beginner-first trader discovery, guided copy setup, MT5 accounts, positions, orders, and trade history.

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

Copy `.env.example` to `.env.local` and provide WorkOS staging credentials:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
NEXT_PUBLIC_STRATEGY_LAB_ENABLED=false
NEXT_PUBLIC_COPY_TRADING_PREVIEW=false

WORKOS_API_KEY=sk_test_replace_me
WORKOS_CLIENT_ID=client_replace_me
WORKOS_COOKIE_PASSWORD=replace-with-at-least-32-random-characters
NEXT_PUBLIC_WORKOS_REDIRECT_URI=http://localhost:3000/auth/callback
DASHBOARD_PROXY_SECRET=replace-with-an-independent-random-secret
```

WorkOS owns identities and AuthKit owns session refresh and sign-out. The application exposes its
own authentication UI while keeping credentials and OAuth exchanges server-side:

- `/sign-in` and `/sign-up` for first-party email/password forms and Google OAuth.
- `/reset-password` for WorkOS password reset links.
- `/auth/callback` as the Google OAuth redirect URI with PKCE and state validation.
- A POST server action for sign-out; there is no state-changing GET logout route.
- An authenticated same-origin `/api/*` proxy. The WorkOS access token remains in
  the encrypted AuthKit cookie and is forwarded server-to-server to FastAPI.
- A short-lived in-memory access token for the direct MT5 WebSocket only. Tokens are
  never persisted to local storage.

Configure the same `DASHBOARD_PROXY_SECRET` on the dashboard and API services.
Configure `WORKOS_CLIENT_ID` on the API so it can validate WebSocket JWTs. The API
also needs `WORKOS_API_KEY` for invitation and user-management actions.

For local WorkOS configuration, register `http://localhost:3000/auth/callback` as a
redirect URI, `http://localhost:3000/sign-in` as the sign-in endpoint,
`http://localhost:3000/sign-up` as the sign-up URL,
`http://localhost:3000/reset-password` as the password reset URL, and
`http://localhost:3000/sign-in` as a sign-out redirect. Production uses the corresponding
HTTPS dashboard URLs. Enable Email + Password and Google OAuth as authentication methods. See the
[AuthKit Next.js SDK](https://github.com/workos/authkit-nextjs) and
[WorkOS invitation guide](https://workos.com/docs/authkit/invitations).

Do not commit real API keys, cookie passwords, or proxy secrets.

## Available Scripts

- `bun run dev` — Start dev server
- `bun run build` — Build production bundle
- `bun run start` — Run production server
- `bun run lint` — Run ESLint
- `bun run test` — Run the Vitest suite

## Copy-trading preview

Use realistic marketplace data without bypassing production authentication:

```bash
NEXT_PUBLIC_COPY_TRADING_PREVIEW=true bun run dev
```

Then open `http://localhost:3000/copy-trading?preview=1`. The build-time flag defaults to `false` and is not enabled in the production Docker image.

## API Integration

The dashboard expects:

- REST endpoints under `/api/*` on the backend
- Account update WebSocket stream at `/ws`

Ensure the API service is running before using data-driven pages.
