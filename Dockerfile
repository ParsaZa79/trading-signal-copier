# =============================================================================
# Multi-stage Dockerfile for Tania Signal Copier
# =============================================================================
# Usage with Dokploy "Docker Build Stage":
#   - API service:       target stage "api"
#   - Dashboard service: target stage "dashboard"
#
# Docker context must be the repo root (.) so both api/ and bot/ are available.
# =============================================================================


# --------------- API Stage ---------------
FROM python:3.13-slim AS api

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy bot source and install bot dependencies
COPY bot/pyproject.toml bot/uv.lock bot/README.md ./bot/
COPY bot/src/ ./bot/src/
COPY bot/scripts/ ./bot/scripts/
RUN mkdir -p ./bot/analysis
WORKDIR /app/bot
RUN uv sync --frozen --no-dev

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

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]


# --------------- Dashboard Stage ---------------
FROM oven/bun:1 AS dashboard

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
RUN bun run build

ENV NODE_ENV=production
EXPOSE 3000

CMD ["bun", "run", "start"]
