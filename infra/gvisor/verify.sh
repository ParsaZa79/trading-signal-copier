#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=infra/gvisor/common.sh
source "$SCRIPT_DIR/common.sh"

init_host_paths
preflight_host

SMOKE_CONTAINER_ID=""
cleanup() {
  local status=$?
  trap - EXIT
  cleanup_smoke_container
  exit "$status"
}
trap cleanup EXIT

verify_runsc_registration
check_health_endpoints "$SCRIPT_DIR/health-contract.json"
smoke_test_runsc

printf 'gVisor %s runtime registration, pinned smoke image, and HTTPS health endpoints passed.\n' "$GVISOR_RELEASE_PIN"
