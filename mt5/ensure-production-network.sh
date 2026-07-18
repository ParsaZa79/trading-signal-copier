#!/usr/bin/env bash
set -euo pipefail

PRIVATE_NETWORK=trading-mt5-api
EGRESS_NETWORK=trading-mt5-egress
VOLUME=trading-mt5-config

if ! docker network inspect "$PRIVATE_NETWORK" >/dev/null 2>&1; then
    docker network create --driver overlay --internal --attachable \
        --label com.tania.security-boundary=mt5-api "$PRIVATE_NETWORK" >/dev/null
fi

read -r internal attachable driver label < <(
    docker network inspect --format \
        '{{.Internal}} {{.Attachable}} {{.Driver}} {{index .Labels "com.tania.security-boundary"}}' \
        "$PRIVATE_NETWORK"
)
if [[ "$internal $attachable $driver $label" != "true true overlay mt5-api" ]]; then
    echo "Refusing incompatible network '$PRIVATE_NETWORK': expected internal=true attachable=true driver=overlay boundary=mt5-api" >&2
    exit 1
fi

if ! docker network inspect "$EGRESS_NETWORK" >/dev/null 2>&1; then
    docker network create --driver bridge --attachable \
        --label com.tania.security-boundary=mt5-egress "$EGRESS_NETWORK" >/dev/null
fi

read -r internal attachable driver label < <(
    docker network inspect --format \
        '{{.Internal}} {{.Attachable}} {{.Driver}} {{index .Labels "com.tania.security-boundary"}}' \
        "$EGRESS_NETWORK"
)
if [[ "$internal $attachable $driver $label" != "false true bridge mt5-egress" ]]; then
    echo "Refusing incompatible network '$EGRESS_NETWORK': expected internal=false attachable=true driver=bridge boundary=mt5-egress" >&2
    exit 1
fi

if ! docker volume inspect "$VOLUME" >/dev/null 2>&1; then
    docker volume create --label com.tania.persistence=mt5-config "$VOLUME" >/dev/null
fi

echo "$PRIVATE_NETWORK, $EGRESS_NETWORK, and $VOLUME are ready"
