#!/usr/bin/env bash
set -Eeuo pipefail

if [[ -n "${GVISOR_RELEASE+x}" ]]; then
  printf 'ERROR: GVISOR_RELEASE override is forbidden.\n' >&2
  exit 2
fi

DRY_RUN="${DRY_RUN-0}"
case "$DRY_RUN" in
  0|1) ;;
  *) printf 'ERROR: DRY_RUN must be exactly 0 or 1.\n' >&2; exit 2 ;;
esac

confirmed=0
requested_state=""
while (($#)); do
  case "$1" in
    --confirm-maintenance)
      confirmed=1
      shift
      ;;
    --state-dir)
      (($# >= 2)) || { printf 'ERROR: --state-dir requires a value.\n' >&2; exit 2; }
      requested_state="$2"
      shift 2
      ;;
    -h|--help)
      printf 'Usage: DRY_RUN=0|1 %s --state-dir PATH [--confirm-maintenance]\n' "$0"
      exit 0
      ;;
    *) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

[[ -n "$requested_state" ]] || { printf 'ERROR: --state-dir is required.\n' >&2; exit 2; }

if [[ "$DRY_RUN" == "1" ]]; then
  printf 'Would validate rollback state %s, validate its daemon configuration, restore all present/absent paths, reload Docker, and verify the original default runtime, workloads, and HTTPS endpoints.\n' "$requested_state"
  printf 'No changes were made.\n'
  exit 0
fi

if [[ "$confirmed" != "1" ]]; then
  printf 'ERROR: rollback is a maintenance action; pass --confirm-maintenance explicitly.\n' >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=infra/gvisor/common.sh
source "$SCRIPT_DIR/common.sh"

init_host_paths
preflight_host
state_dir="$(validate_state_dir "$requested_state")"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

restore_state "$state_dir" "$work_dir"
printf 'Rollback restored and verified the pre-install Docker runtime and workload state from %s.\n' "$state_dir"
