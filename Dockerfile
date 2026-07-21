# =============================================================================
# Multi-stage Dockerfile for Signal Copier
# =============================================================================
# Usage with Dokploy "Docker Build Stage":
#   - API service:       target stage "api"
#   - Dashboard service: target stage "dashboard"
#
# Docker context must be the repo root (.).
# =============================================================================


# --------------- API Stage ---------------
FROM python:3.13.14-slim-bookworm AS api

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /usr/local/bin/uv

WORKDIR /app

# Copy API source and install dependencies
COPY api/pyproject.toml api/uv.lock /app/api/
WORKDIR /app/api
RUN uv sync --frozen --no-dev

COPY api/src/ ./src/
COPY api/alembic.ini ./alembic.ini
COPY api/alembic/ ./alembic/

RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=3)"

CMD ["sh", "-c", "if [ -n \"$DATABASE_URL\" ] && printf '%s' \"$DATABASE_URL\" | grep -q '^postgresql'; then uv run --no-sync alembic upgrade head; fi; exec uv run --no-sync uvicorn src.main:app --host 0.0.0.0 --port 8000"]


# --------------- Dashboard Build Stage ---------------
FROM oven/bun:1.3.4 AS dashboard-build

WORKDIR /app
COPY dashboard/package.json dashboard/bun.lock ./
RUN bun install --frozen-lockfile
COPY dashboard/ .

# Next.js inlines NEXT_PUBLIC_* at build time.
ARG NEXT_PUBLIC_API_URL=https://api.kiaparsaprintingmoneymachine.cloud
ARG NEXT_PUBLIC_WS_URL=wss://api.kiaparsaprintingmoneymachine.cloud/ws
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_STRATEGY_LAB_ENABLED=false
ARG NEXT_PUBLIC_BETTER_AUTH_ENABLED=false
ARG NEXT_PUBLIC_OPEN_SIGNUP_ENABLED=false
ARG NEXT_PUBLIC_TURNSTILE_SITE_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_STRATEGY_LAB_ENABLED=$NEXT_PUBLIC_STRATEGY_LAB_ENABLED
ENV NEXT_PUBLIC_BETTER_AUTH_ENABLED=$NEXT_PUBLIC_BETTER_AUTH_ENABLED
ENV NEXT_PUBLIC_OPEN_SIGNUP_ENABLED=$NEXT_PUBLIC_OPEN_SIGNUP_ENABLED
ENV NEXT_PUBLIC_TURNSTILE_SITE_KEY=$NEXT_PUBLIC_TURNSTILE_SITE_KEY
ENV NEXT_TELEMETRY_DISABLED=1
RUN bun run build

# --------------- Dashboard Runtime Stage ---------------
# Keep the Dokploy target name `dashboard`, but export only Next.js' traced
# standalone server instead of the ~1 GB build-time dependency tree.
FROM oven/bun:1.3.4 AS dashboard

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

COPY --from=dashboard-build --chown=bun:bun /app/public ./public
COPY --from=dashboard-build --chown=bun:bun /app/.next/standalone ./
COPY --from=dashboard-build --chown=bun:bun /app/.next/static ./.next/static

USER bun
EXPOSE 3000

CMD ["bun", "server.js"]
