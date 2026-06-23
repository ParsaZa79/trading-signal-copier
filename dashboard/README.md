# Trading Dashboard (Next.js)

Frontend UI for monitoring account performance, open positions, orders, trade history, and bot status/control.

## Requirements

- Node.js 20+
- npm (or compatible package manager)
- Running backend API (`api/`) on port `8000` by default

## Setup

```bash
cd dashboard
npm install
```

## Run (Development)

```bash
cd dashboard
npm run dev
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
```

If omitted, these defaults are used by `src/lib/constants.ts`.
If `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set, the dashboard uses Clerk sign-in/sign-up
pages and route protection. The dashboard server needs `CLERK_SECRET_KEY`, and the
dashboard plus API must share the same `DASHBOARD_PROXY_SECRET`.

## Available Scripts

- `npm run dev` — Start dev server
- `npm run build` — Build production bundle
- `npm run start` — Run production server
- `npm run lint` — Run ESLint

## API Integration

The dashboard expects:

- REST endpoints under `/api/*` on the backend
- WebSocket streams at `/ws` and `/ws/logs`

Ensure the API service is running before using data-driven pages.
