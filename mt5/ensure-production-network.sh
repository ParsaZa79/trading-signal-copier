#!/usr/bin/env bash
set -euo pipefail

NETWORK=trading-mt5-api

if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
    docker network create --driver bridge --internal --attachable \
        --label com.tania.security-boundary=mt5-api "$NETWORK" >/dev/null
fi

read -r internal attachable driver label < <(
    docker network inspect --format \
        '{{.Internal}} {{.Attachable}} {{.Driver}} {{index .Labels "com.tania.security-boundary"}}' \
        "$NETWORK"
)
if [[ "$internal $attachable $driver $label" != "true true bridge mt5-api" ]]; then
    echo "Refusing incompatible network '$NETWORK': expected internal=true attachable=true driver=bridge boundary=mt5-api" >&2
    exit 1
fi
echo "$NETWORK is ready"
