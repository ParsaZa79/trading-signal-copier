#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
readonly BASE_COMPOSE="${SCRIPT_DIR}/compose.yaml"
readonly BOOTSTRAP_COMPOSE="${SCRIPT_DIR}/compose.bootstrap.yaml"
readonly RECOVERY_COMPOSE="${SCRIPT_DIR}/compose.recovery.yaml"
readonly TLS_MOUNTED_COMPOSE="${SCRIPT_DIR}/compose.tls-mounted.yaml"
readonly COMPOSE_PROJECT="trading-platform-mail"

usage() {
  cat <<'EOF'
Usage:
  bootstrap.sh start    --confirm-maintenance
  bootstrap.sh recovery --confirm-maintenance [--tls-mounted]
  bootstrap.sh remove   --confirm-maintenance [--tls-mounted]

start     Recreate Stalwart in first-boot mode on an isolated bridge with a
          loopback-only admin port. Complete the setup wizard, then use recovery.
recovery  Recreate the same isolated service with STALWART_RECOVERY_MODE=1 so
          listeners/TLS can be configured and verified after the wizard restart.
remove    Recreate Stalwart from the production base, then prove that recovery
          environment names and the host admin binding are absent.

STALWART_RECOVERY_ADMIN must be set for start/recovery. Every operation changes
a running service and requires the literal confirmation flag.
--tls-mounted is only for the external-ACME fallback. It keeps the read-only
certificate volume attached through recovery and final base recreation.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

[[ $# -ge 2 && $# -le 3 ]] || {
  usage >&2
  exit 2
}

readonly ACTION="$1"
shift
confirmed=0
tls_mounted=0
for argument in "$@"; do
  case "$argument" in
    --confirm-maintenance) confirmed=1 ;;
    --tls-mounted) tls_mounted=1 ;;
    *) die "unknown argument: $argument" ;;
  esac
done
[[ "$confirmed" == "1" ]] || die "refusing service mutation without --confirm-maintenance"
[[ "$ACTION" == "start" || "$ACTION" == "recovery" || "$ACTION" == "remove" ]] || \
  die "action must be 'start', 'recovery', or 'remove'"
[[ "$ACTION" != "start" || "$tls_mounted" == "0" ]] || \
  die "--tls-mounted is allowed only for recovery and remove"
readonly USE_TLS_MOUNTED="$tls_mounted"

command -v docker >/dev/null 2>&1 || die "docker command is required"
command -v grep >/dev/null 2>&1 || die "grep command is required"
command -v python3 >/dev/null 2>&1 || die "python3 command is required"
docker compose version >/dev/null 2>&1 || die "docker compose plugin is required"

container_id() {
  local compose_file="$1"
  local id
  id="$(docker compose --project-name "$COMPOSE_PROJECT" -f "$compose_file" ps -q stalwart)"
  [[ -n "$id" ]] || die "Stalwart container was not found after recreation"
  printf '%s\n' "$id"
}

environment_names() {
  local id="$1"

  # Consume the raw environment only through a pipe and emit names, never values.
  docker inspect --format '{{json .Config.Env}}' "$id" | python3 -c '
import json
import sys

try:
    values = json.load(sys.stdin)
except json.JSONDecodeError as exc:
    raise SystemExit(f"could not parse container environment metadata: {exc.msg}")
if not isinstance(values, list):
    raise SystemExit("container environment metadata is not a list")
for value in values:
    if isinstance(value, str):
        print(value.partition("=")[0])
'
}

admin_host_binding_state() {
  local id="$1"

  docker inspect --format '{{json .HostConfig.PortBindings}}' "$id" | python3 -c '
import json
import sys

try:
    bindings = json.load(sys.stdin)
except json.JSONDecodeError as exc:
    raise SystemExit(f"could not parse container port metadata: {exc.msg}")
if bindings is None:
    bindings = {}
if not isinstance(bindings, dict):
    raise SystemExit("container port metadata is not an object")
admin = bindings.get("8080/tcp")
if admin is None:
    print("absent")
elif (
    isinstance(admin, list)
    and len(admin) == 1
    and isinstance(admin[0], dict)
    and admin[0].get("HostIp") == "127.0.0.1"
    and admin[0].get("HostPort") == "18080"
):
    print("safe")
else:
    print("unsafe")
'
}

bootstrap_network_state() {
  local id="$1"

  docker inspect --format '{{json .NetworkSettings.Networks}}' "$id" | python3 -c '
import json
import sys

try:
    networks = json.load(sys.stdin)
except json.JSONDecodeError as exc:
    raise SystemExit(f"could not parse container network metadata: {exc.msg}")
if not isinstance(networks, dict):
    raise SystemExit("container network metadata is not an object")
names = list(networks)
safe = (
    len(names) == 1
    and names[0] != "trading-platform-mail"
    and names[0].endswith("_bootstrap-admin")
)
print("safe" if safe else "unsafe")
'
}

require_safe_loopback_publishing() {
  local engine_version major
  engine_version="$(docker version --format '{{.Server.Version}}')" || \
    die "could not read Docker Engine server version"
  [[ "$engine_version" =~ ^([0-9]+)(\.|$) ]] || \
    die "could not parse Docker Engine server version"
  major="${BASH_REMATCH[1]}"
  (( major >= 28 )) || \
    die "Docker Engine 28.0.0 or newer is required for safe loopback port publishing"
}

require_recovery_credential() {
  local recovery_user recovery_password
  [[ -n "${STALWART_RECOVERY_ADMIN:-}" ]] || \
    die "STALWART_RECOVERY_ADMIN must be set for bootstrap/recovery"
  [[ "$STALWART_RECOVERY_ADMIN" == *:* ]] || \
    die "STALWART_RECOVERY_ADMIN must use the documented user:password form"
  recovery_user="${STALWART_RECOVERY_ADMIN%%:*}"
  recovery_password="${STALWART_RECOVERY_ADMIN#*:}"
  [[ -n "$recovery_user" && -n "$recovery_password" ]] || \
    die "STALWART_RECOVERY_ADMIN requires a non-empty user and password"
}

fail_with_compose_cleanup() {
  local reason="$1"
  shift

  if docker compose "$@" down --remove-orphans >/dev/null 2>&1; then
    die "${reason}; the suspect Stalwart container was removed"
  fi
  die "CRITICAL: ${reason}; fail-closed cleanup also failed and the suspect Stalwart container may remain"
}

verify_isolated_admin() {
  local id="$1"
  local require_mode="$2"
  local names

  names="$(environment_names "$id")"
  grep -Fxq 'STALWART_RECOVERY_ADMIN' <<<"$names" || \
    die "bootstrap recovery environment name is missing after recreation"
  if [[ "$require_mode" == "1" ]]; then
    grep -Fxq 'STALWART_RECOVERY_MODE' <<<"$names" || \
      die "explicit recovery mode is missing after recreation"
  elif grep -Fxq 'STALWART_RECOVERY_MODE' <<<"$names"; then
    die "first-boot action unexpectedly enabled recovery mode"
  fi
  [[ "$(admin_host_binding_state "$id")" == "safe" ]] || \
    die "bootstrap admin is not bound only to 127.0.0.1:18080"
  [[ "$(bootstrap_network_state "$id")" == "safe" ]] || \
    die "Stalwart is not attached only to the isolated bootstrap network"
}

verify_recovery_absent() {
  local id="$1"
  local names
  names="$(environment_names "$id")"
  if grep -Eq '^(STALWART_RECOVERY_ADMIN|STALWART_RECOVERY_MODE)$' <<<"$names"; then
    die "bootstrap recovery environment is still present after base recreation"
  fi
  [[ "$(admin_host_binding_state "$id")" == "absent" ]] || \
    die "bootstrap admin container port 8080 is still bound on the host"
}

start_isolated() {
  local require_mode="$1"
  local isolated_id
  local -a compose_arguments=(
    --project-name "$COMPOSE_PROJECT"
    -f "$BOOTSTRAP_COMPOSE"
  )
  if [[ "$require_mode" == "1" ]]; then
    compose_arguments+=( -f "$RECOVERY_COMPOSE" )
    if [[ "$USE_TLS_MOUNTED" == "1" ]]; then
      compose_arguments+=( -f "$TLS_MOUNTED_COMPOSE" )
    fi
  fi

  require_recovery_credential
  require_safe_loopback_publishing
  if ! docker compose "${compose_arguments[@]}" up -d --force-recreate stalwart; then
    fail_with_compose_cleanup \
      "isolated bootstrap/recovery recreation failed" "${compose_arguments[@]}"
  fi
  if ! isolated_id="$(container_id "$BOOTSTRAP_COMPOSE")"; then
    fail_with_compose_cleanup \
      "isolated bootstrap/recovery container lookup failed" "${compose_arguments[@]}"
  fi
  if ! (verify_isolated_admin "$isolated_id" "$require_mode"); then
    fail_with_compose_cleanup \
      "isolated bootstrap/recovery verification failed" "${compose_arguments[@]}"
  fi
}

case "$ACTION" in
  start)
    start_isolated 0
    printf '%s\n' \
      'First-boot admin is available on 127.0.0.1:18080 over the isolated bridge.' \
      'Complete the wizard; after its restart run bootstrap.sh recovery --confirm-maintenance.'
    ;;
  recovery)
    start_isolated 1
    recovery_remove_command='bootstrap.sh remove --confirm-maintenance'
    if [[ "$USE_TLS_MOUNTED" == "1" ]]; then
      recovery_remove_command+=' --tls-mounted'
    fi
    printf '%s\n' \
      'Explicit recovery mode is available on 127.0.0.1:18080 over the isolated bridge.' \
      "Apply and verify final listeners/TLS, then run ${recovery_remove_command}."
    ;;
  remove)
    unset STALWART_RECOVERY_ADMIN STALWART_RECOVERY_MODE
    base_arguments=(--project-name "$COMPOSE_PROJECT" -f "$BASE_COMPOSE")
    if [[ "$USE_TLS_MOUNTED" == "1" ]]; then
      base_arguments+=( -f "$TLS_MOUNTED_COMPOSE" )
    fi
    if ! docker compose "${base_arguments[@]}" up -d --force-recreate stalwart; then
      fail_with_compose_cleanup "base recreation failed" "${base_arguments[@]}"
    fi
    if ! base_id="$(container_id "$BASE_COMPOSE")"; then
      fail_with_compose_cleanup "base container lookup failed" "${base_arguments[@]}"
    fi
    if ! (verify_recovery_absent "$base_id"); then
      fail_with_compose_cleanup "bootstrap removal proof failed" "${base_arguments[@]}"
    fi
    printf '%s\n' \
      'Bootstrap disabled: recovery environment names and the host admin binding are absent.'
    ;;
esac
