#!/usr/bin/env bash
set -Eeuo pipefail

# Immutable release pin: 20260706.0. GVISOR_RELEASE is deliberately not a
# supported override; updating this file and its reviewed SHA-512 constants is
# the only release-change path.
if [[ -n "${GVISOR_RELEASE+x}" ]]; then
  printf 'ERROR: GVISOR_RELEASE override is forbidden; update the reviewed release pin instead.\n' >&2
  exit 2
fi

DRY_RUN="${DRY_RUN-0}"
case "$DRY_RUN" in
  0|1) ;;
  *) printf 'ERROR: DRY_RUN must be exactly 0 or 1.\n' >&2; exit 2 ;;
esac

confirmed=0
for argument in "$@"; do
  case "$argument" in
    --confirm-maintenance) confirmed=1 ;;
    -h|--help)
      printf 'Usage: DRY_RUN=0|1 %s [--confirm-maintenance]\n' "$0"
      exit 0
      ;;
    *) printf 'ERROR: unknown argument: %s\n' "$argument" >&2; exit 2 ;;
  esac
done

if [[ "$DRY_RUN" == "1" ]]; then
  cat <<'EOF'
Would preflight Linux, kernel, Docker 23+, the default local Unix-socket context, systemd reload support, sudo, tools, and dockerd flags.
Would download release 20260706.0 artifacts and verify their embedded SHA-512 digests.
Would validate a candidate daemon.json, capture the default runtime, running workloads, and HTTPS health endpoints.
Would preserve daemon.json and both prior binaries (including absent-file sentinels) in root-owned, integrity-checked rollback state before mutation.
Would add only the runsc runtime, reload Docker, run a digest-pinned smoke container, and verify all captured health invariants.
A command, reload, or verification failure, or handled HUP/INT/TERM after mutation, would trigger an automatic rollback attempt.
A rollback verification failure would be reported as critical; SIGKILL and host/power loss cannot be trapped.
No changes were made.
EOF
  exit 0
fi

if [[ "$confirmed" != "1" ]]; then
  printf 'ERROR: installation is a maintenance action; pass --confirm-maintenance explicitly.\n' >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=infra/gvisor/common.sh
source "$SCRIPT_DIR/common.sh"

init_host_paths
preflight_host

raw_arch="$(uname -m)"
case "$raw_arch" in
  x86_64)
    arch="x86_64"
    runsc_sha512="73938c145ebe554cf61a01da455688f4b732eebdf7b1b635bdef5b195868b363d8cb400e3d92ed1f377b78996805556c247a4849583910cb04e92b156053033e"
    shim_sha512="6f1b34266ed3ab503f6e88116dd97d0fb5f79311ea174059dd284de11b36ee062649da2fe3dccea9e2d25abe4df04bee5ee443ec0b9348ae44e63fabda28e8f8"
    ;;
  aarch64|arm64)
    arch="aarch64"
    runsc_sha512="a4962fe56ee62c841c270443a3617b6626db3fb282e65793f6762df78b3209304dfe2e094e524b3d2b4c781c05b1b95744ce9fe50b49edee43090b27c2956c4b"
    shim_sha512="2ddb4eacc5a30e2aadf882b6dfa86b579ce46861f0cd13bc415c18b88d9c4d8309ec0bc7ddfe741b2fb5747af6c9f2f736e2169c1a46fb6f1a227f4b8962a88b"
    ;;
  *) die "unsupported architecture: $raw_arch" ;;
esac

work_dir="$(mktemp -d)"
state_dir=""
mutation_started=0
SMOKE_CONTAINER_ID=""

cleanup() {
  local status=$?
  trap - EXIT
  cleanup_smoke_container
  rm -rf "$work_dir"
  exit "$status"
}

rollback_and_exit() {
  local status="$1"
  local reason="$2"
  trap - ERR
  trap '' HUP INT TERM
  cleanup_smoke_container
  if [[ "$mutation_started" == "1" && -n "$state_dir" ]]; then
    printf '%s; starting automatic rollback from %s.\n' "$reason" "$state_dir" >&2
    if restore_state "$state_dir" "$work_dir"; then
      printf 'Automatic rollback completed and prior runtime/workload health was verified.\n' >&2
    else
      printf 'CRITICAL: automatic rollback could not be fully verified; keep the maintenance window open and use rollback.sh with this state: %s\n' "$state_dir" >&2
    fi
  fi
  exit "$status"
}

automatic_rollback() {
  local status=$?
  rollback_and_exit "$status" 'A maintenance step failed'
}

signal_rollback() {
  local signal_name="$1"
  local status="$2"
  rollback_and_exit "$status" "Signal $signal_name interrupted maintenance"
}

trap cleanup EXIT
trap automatic_rollback ERR
trap 'signal_rollback HUP 129' HUP
trap 'signal_rollback INT 130' INT
trap 'signal_rollback TERM 143' TERM

base_url="https://storage.googleapis.com/gvisor/releases/release/${GVISOR_RELEASE_PIN}/${arch}"
curl --fail --silent --show-error --location --max-time 120 --output "$work_dir/runsc" "$base_url/runsc"
curl --fail --silent --show-error --location --max-time 120 --output "$work_dir/containerd-shim-runsc-v1" "$base_url/containerd-shim-runsc-v1"
printf '%s  %s\n' "$runsc_sha512" "$work_dir/runsc" | sha512sum --check --strict -
printf '%s  %s\n' "$shim_sha512" "$work_dir/containerd-shim-runsc-v1" | sha512sum --check --strict -
chmod 0755 "$work_dir/runsc" "$work_dir/containerd-shim-runsc-v1"

daemon_classification="$(classify_host_path "$DAEMON_CONFIG" regular)"
read -r daemon_state daemon_mode daemon_uid daemon_gid <<< "$daemon_classification"
if [[ "$daemon_state" == "regular" ]]; then
  run_root cat "$DAEMON_CONFIG" > "$work_dir/daemon.original.json"
elif [[ "$daemon_state" == "absent" ]]; then
  daemon_mode='0600'
  daemon_uid="$STATE_OWNER_UID"
  daemon_gid="$STATE_OWNER_GID"
  printf '{}\n' > "$work_dir/daemon.original.json"
else
  die "unexpected daemon configuration path classification: $daemon_state"
fi
python3 - "$work_dir/daemon.original.json" "$work_dir/daemon.candidate.json" <<'PY'
import json
import pathlib
import sys

source, destination = map(pathlib.Path, sys.argv[1:])
with source.open(encoding="utf-8") as handle:
    config = json.load(handle)
if not isinstance(config, dict):
    raise SystemExit("daemon.json must contain a JSON object")
runtimes = config.setdefault("runtimes", {})
if not isinstance(runtimes, dict):
    raise SystemExit("daemon.json runtimes must be a JSON object")
runtimes["runsc"] = {"path": "/usr/local/bin/runsc"}
destination.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
validate_docker_config "$work_dir/daemon.candidate.json"

read_default_runtime > "$work_dir/default-runtime.before"
capture_workloads "$work_dir/workloads-before"
cp -p "$work_dir/workloads-before/container-ids.txt" "$work_dir/container-ids.txt"
cp -p "$work_dir/workloads-before/containers.jsonl" "$work_dir/containers.jsonl"
cp -p "$work_dir/workloads-before/container-state.txt" "$work_dir/container-state.txt"
health_contract_file="$SCRIPT_DIR/health-contract.json"
check_health_endpoints "$health_contract_file"

if [[ "${GVISOR_TEST_MODE:-0}" == "1" ]]; then
  timestamp="${GVISOR_TEST_TIMESTAMP:?GVISOR_TEST_TIMESTAMP is required in test mode}"
else
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
fi
[[ "$timestamp" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || die "invalid state timestamp: $timestamp"
state_dir="$STATE_ROOT/$GVISOR_RELEASE_PIN/$timestamp"
create_state_backup "$state_dir" "$work_dir" "$health_contract_file"

mutation_started=1
run_root rm -f "$RUNSC_PATH"
run_root rm -f "$SHIM_PATH"
run_root install -m 0755 "$work_dir/runsc" "$RUNSC_PATH"
run_root install -m 0755 "$work_dir/containerd-shim-runsc-v1" "$SHIM_PATH"
run_root install -m "$daemon_mode" -o "$daemon_uid" -g "$daemon_gid" \
  "$work_dir/daemon.candidate.json" "$DAEMON_CONFIG"
run_root dockerd --validate --config-file="$DAEMON_CONFIG"
run_root systemctl reload docker

verify_runsc_registration
verify_default_runtime_unchanged "$state_dir"
verify_captured_workloads "$state_dir"
check_captured_health_endpoints "$state_dir"
smoke_test_runsc

mutation_started=0
trap - ERR
printf 'gVisor %s was added as an opt-in Docker runtime; the default runtime and existing workload health are unchanged.\n' "$GVISOR_RELEASE_PIN"
printf 'Rollback state: %s\n' "$state_dir"
