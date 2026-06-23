# Deployment Topology Snapshot

Snapshot captured from local repo plus authenticated Dokploy read-only API on 2026-06-23. Verify live before acting.

## Project

- Dokploy URL: `https://www.kiaparsaprintingmoneymachine.cloud`
- Project: `Trading Platform`
- Project ID: `7pc-S-pskmHQGUOsyr-jg`
- Environment: `production`
- Environment ID: `KBRvjhnhe9MFeEo5lcUqB`

## Services

### trading-api

- Type: Dokploy application
- Application ID: `Y3u4LAcWy6f-2Raehj4dN`
- App/container name: `trading-platform-tradingapi-oicmxn`
- Source type: `github`
- Owner/repository as recorded by Dokploy: `ParsaZa79/tania-signal-copier`
- Branch: `main`
- Build type: `dockerfile`
- Docker build stage: `api`
- Docker context path: repo root
- Auto deploy: enabled
- Public domain: `https://api.kiaparsaprintingmoneymachine.cloud`
- Traefik target: `http://trading-platform-tradingapi-oicmxn:8000`
- Important non-secret env:
  - `MT5_DOCKER_HOST=mt5`
  - `MT5_DOCKER_PORT=8001`
  - `CORS_ORIGINS=https://dashboard.kiaparsaprintingmoneymachine.cloud`
  - `BOT_DATA_DIR=/app/data`
- Secret env keys exist for MT5 credentials. Redact values.
- Bind mounts:
  - `/home/parsa/telegram-session/signal_bot_session.session` -> `/app/bot/signal_bot_session.session`
  - `/home/parsa/telegram-session` -> `/app/data`

### trading-dashboard

- Type: Dokploy application
- Application ID: `lku4v_DVjO_BEJSSQgBZi`
- App/container name: `trading-platform-tradingdashboard-j14t76`
- Source type: `github`
- Owner/repository as recorded by Dokploy: `ParsaZa79/tania-signal-copier`
- Branch: `main`
- Build type: `dockerfile`
- Docker build stage: `dashboard`
- Docker context path: repo root
- Auto deploy: enabled
- Public domain: `https://dashboard.kiaparsaprintingmoneymachine.cloud`
- Traefik target: `http://trading-platform-tradingdashboard-j14t76:3000`
- Important env:
  - `NEXT_PUBLIC_API_URL=https://api.kiaparsaprintingmoneymachine.cloud`
  - `NEXT_PUBLIC_WS_URL=wss://api.kiaparsaprintingmoneymachine.cloud/ws`
  - `NODE_ENV=production`

### mt5docker

- Type: Dokploy raw compose service
- Compose ID: `lyWoSktldNGDOg1ijVsrk`
- App/container name: `trading-platform-mt5docker-1uotpe`
- Source type: `raw`
- Image: `gmag11/metatrader5_vnc:latest`
- Host ports:
  - `3001:3000` for VNC
  - `8001:8001` for RPyC server
- Volume: `mt5-config:/config`
- Network: external `dokploy-network`
- Compose env includes VNC password. Redact value.
- Service is named `mt5` in compose; this is why API uses `MT5_DOCKER_HOST=mt5`.

Compose file shape:

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

## Dockerfile Contract

Repo root `Dockerfile` defines two Dokploy build targets:

- `api`: Python/uv image. Copies bot source, bot scripts, API source. Creates `/app/data`. Exposes `8000`. Runs Uvicorn.
- `dashboard`: Bun image. Builds Next.js with production `NEXT_PUBLIC_*` URLs. Exposes `3000`. Runs `bun run start`.

## Deployment Drift Check

On 2026-06-23:

- Latest successful Dokploy deployments seen for `trading-api` and `trading-dashboard`: commit `4ca08a0d60c2c6c4dc899304c63cf64f85fa2ea3`, title `Skip partial close when it would fully close position`, created 2026-03-04.
- Local `main` was at `ac774eb289d5f732092e2902deb59ad955c5a634`, three commits ahead of `4ca08a0`.
- The live dashboard HTML matched the older `4ca08a0` sidebar branding (`TradingBot`), not the newer local `Signal Copier` sidebar. Treat production as stale until a new successful deployment proves otherwise.

## Health Check

The API health endpoint is:

```text
https://api.kiaparsaprintingmoneymachine.cloud/api/health/
```

On 2026-06-23 it returned HTTP 200 with `status: unhealthy` because MT5 was not connected. Separate this runtime state from deployment correctness.
