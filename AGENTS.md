# Agent Notes

## Dokploy Deployment

This repo is deployed on Dokploy. Treat Dokploy as production: inspect read-only by default, redact secrets, and do not deploy/redeploy/stop/start/update services unless the user explicitly asks.

Snapshot below was verified from the local repo plus authenticated Dokploy read-only API on 2026-06-23. Re-check live state before acting because Dokploy and Git can drift.

### Project

- Dokploy URL: `https://www.kiaparsaprintingmoneymachine.cloud`
- Project: `Trading Platform`
- Project ID: `7pc-S-pskmHQGUOsyr-jg`
- Environment: `production`
- Environment ID: `KBRvjhnhe9MFeEo5lcUqB`

### Services

#### `trading-api`

- Dokploy type: application
- Application ID: `Y3u4LAcWy6f-2Raehj4dN`
- App/container name: `trading-platform-tradingapi-oicmxn`
- Source type: GitHub
- Dokploy recorded source: `ParsaZa79/tania-signal-copier`, branch `main`
- Build type: Dockerfile
- Docker build stage: `api`
- Docker context: repo root
- Auto deploy: enabled
- Public URL: `https://api.kiaparsaprintingmoneymachine.cloud`
- Traefik target: `http://trading-platform-tradingapi-oicmxn:8000`
- Non-secret env:
  - `MT5_DOCKER_HOST=mt5`
  - `MT5_DOCKER_PORT=8001`
  - `CORS_ORIGINS=https://dashboard.kiaparsaprintingmoneymachine.cloud`
  - `BOT_DATA_DIR=/app/data`
- Secret env keys exist for MT5 credentials. Never print their values.
- Bind mounts:
  - `/home/parsa/telegram-session/signal_bot_session.session` -> `/app/bot/signal_bot_session.session`
  - `/home/parsa/telegram-session` -> `/app/data`

#### `trading-dashboard`

- Dokploy type: application
- Application ID: `lku4v_DVjO_BEJSSQgBZi`
- App/container name: `trading-platform-tradingdashboard-j14t76`
- Source type: GitHub
- Dokploy recorded source: `ParsaZa79/tania-signal-copier`, branch `main`
- Build type: Dockerfile
- Docker build stage: `dashboard`
- Docker context: repo root
- Auto deploy: enabled
- Public URL: `https://dashboard.kiaparsaprintingmoneymachine.cloud`
- Traefik target: `http://trading-platform-tradingdashboard-j14t76:3000`
- Env:
  - `NEXT_PUBLIC_API_URL=https://api.kiaparsaprintingmoneymachine.cloud`
  - `NEXT_PUBLIC_WS_URL=wss://api.kiaparsaprintingmoneymachine.cloud/ws`
  - `NODE_ENV=production`

#### `mt5docker`

- Dokploy type: raw compose service
- Compose ID: `lyWoSktldNGDOg1ijVsrk`
- App/container name: `trading-platform-mt5docker-1uotpe`
- Source type: raw
- Image: `gmag11/metatrader5_vnc:latest`
- Service name inside compose: `mt5`
- Host ports:
  - `3001:3000` for VNC
  - `8001:8001` for RPyC
- Volume: `mt5-config:/config`
- Network: external `dokploy-network`
- Compose env includes the VNC password. Never print its value.

Compose shape:

```yaml
services:
  mt5:
    image: gmag11/metatrader5_vnc:latest
    ports:
      - "3001:3000"
      - "8001:8001"
    volumes:
      - mt5-config:/config
    environment:
      - CUSTOM_USER=parsa
      - PASSWORD=${MT5_VNC_PASSWORD}
    networks:
      - dokploy-network

networks:
  dokploy-network:
    external: true

volumes:
  mt5-config:
```

### Dockerfile Contract

The root `Dockerfile` is a multi-stage Dockerfile for Dokploy:

- Stage `api`: Python/uv image, installs bot dependencies and API dependencies, copies bot scripts and API source, creates `/app/data`, exposes `8000`, runs Uvicorn.
- Stage `dashboard`: Bun image, installs dashboard dependencies, builds Next.js with production `NEXT_PUBLIC_*` URLs, exposes `3000`, runs `bun run start`.

### Deployment Drift

As of 2026-06-23, the latest successful Dokploy deployments observed for both `trading-api` and `trading-dashboard` were at commit `4ca08a0d60c2c6c4dc899304c63cf64f85fa2ea3` (`Skip partial close when it would fully close position`) from 2026-03-04.

Local `main` at that time was `ac774eb289d5f732092e2902deb59ad955c5a634`, three commits ahead of the recorded production deployment. The live dashboard HTML matched the older `4ca08a0` branding (`TradingBot`), not the newer local `Signal Copier` sidebar. Treat production as stale until a new successful Dokploy deployment proves otherwise.

Also note the local Git remote is `ParsaZa79/trading-signal-copier.git`, while Dokploy recorded `ParsaZa79/tania-signal-copier`. This may be a repository rename, but verify before relying on auto-deploy.

### Useful Read-Only Checks

```bash
dokploy --version
dokploy project all --json
dokploy deployment all-centralized --json
curl -sS -D - https://api.kiaparsaprintingmoneymachine.cloud/api/health/ -o /tmp/trading-api-health.txt
curl -sS -I https://dashboard.kiaparsaprintingmoneymachine.cloud
```

The API health endpoint is `https://api.kiaparsaprintingmoneymachine.cloud/api/health/`. On 2026-06-23 it returned HTTP 200 with `status: unhealthy` because MT5 was not connected. Separate runtime MT5 connectivity from deployment configuration.

### Dokploy CLI Quirk

The installed `dokploy` CLI observed here was version `0.3.0`. Several generated read/detail commands can fail with HTTP 400 because the CLI sends tRPC GET input as:

```json
{"applicationId":"..."}
```

The server expects:

```json
{"json":{"applicationId":"..."}}
```

If `dokploy application one`, `dokploy compose one`, domain detail, or mount detail commands fail with HTTP 400, use a wrapped tRPC request or the repo-local skill helper at `.codex/skills/dokploy-trading-signal-copier/scripts/dokploy_read.mjs` for sanitized read-only inspection.
