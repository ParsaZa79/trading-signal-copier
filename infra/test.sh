#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${ROOT_DIR}/infra"
STALWART_DIR="${INFRA_DIR}/stalwart"

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    printf 'error: required command not found: %s\n' "${command_name}" >&2
    exit 1
  fi
}

run_compose_config() {
  local variant="$1"
  shift
  printf '==> Compose config: %s\n' "${variant}"
  docker compose \
    --project-directory "${STALWART_DIR}" \
    --project-name "infra-validation-${variant}" \
    --env-file /dev/null \
    "$@" \
    config --quiet
}

require_command bash
require_command docker
require_command uv

if ! docker compose version >/dev/null 2>&1; then
  printf 'error: Docker Compose v2 (docker compose) is required\n' >&2
  exit 1
fi

printf '==> Infra parsed and mocked tests\n'
uv run --project "${INFRA_DIR}" --frozen \
  pytest --quiet "${INFRA_DIR}/tests"

shell_scripts=()
shellcheck_scripts=()
while IFS= read -r script; do
  shell_scripts+=("${script}")
  if [[ "${script}" != "${INFRA_DIR}/gvisor/common.sh" ]]; then
    shellcheck_scripts+=("${script}")
  fi
done < <(find "${INFRA_DIR}" -type f -name '*.sh' -print | LC_ALL=C sort)

if ((${#shell_scripts[@]} == 0)); then
  printf 'error: no infra shell scripts found\n' >&2
  exit 1
fi

printf '==> Bash syntax (%d scripts)\n' "${#shell_scripts[@]}"
for script in "${shell_scripts[@]}"; do
  bash -n "${script}"
done

if command -v shellcheck >/dev/null 2>&1; then
  printf '==> ShellCheck (%d entry scripts; common.sh via source directives)\n' \
    "${#shellcheck_scripts[@]}"
  shellcheck --external-sources "${shellcheck_scripts[@]}"
elif [[ "${CI:-}" == "true" || "${CI:-}" == "1" ]]; then
  printf 'error: ShellCheck is required in CI\n' >&2
  exit 1
else
  printf '==> ShellCheck skipped locally: install shellcheck to enable it\n'
fi

run_compose_config base \
  --file "${STALWART_DIR}/compose.yaml"

printf '==> Compose config: bootstrap\n'
env \
  STALWART_RECOVERY_ADMIN='admin:compose-validation-placeholder-not-a-secret' \
  docker compose \
    --project-directory "${STALWART_DIR}" \
    --project-name infra-validation-bootstrap \
    --env-file /dev/null \
    --file "${STALWART_DIR}/compose.bootstrap.yaml" \
    config --quiet

printf '==> Compose config: recovery\n'
env \
  STALWART_RECOVERY_ADMIN='admin:compose-validation-placeholder-not-a-secret' \
  docker compose \
    --project-directory "${STALWART_DIR}" \
    --project-name infra-validation-recovery \
    --env-file /dev/null \
    --file "${STALWART_DIR}/compose.bootstrap.yaml" \
    --file "${STALWART_DIR}/compose.recovery.yaml" \
    config --quiet

printf '==> Compose config: recovery-tls-mounted\n'
env \
  STALWART_RECOVERY_ADMIN='admin:compose-validation-placeholder-not-a-secret' \
  docker compose \
    --project-directory "${STALWART_DIR}" \
    --project-name infra-validation-recovery-tls-mounted \
    --env-file /dev/null \
    --file "${STALWART_DIR}/compose.bootstrap.yaml" \
    --file "${STALWART_DIR}/compose.recovery.yaml" \
    --file "${STALWART_DIR}/compose.tls-mounted.yaml" \
    config --quiet

run_compose_config local \
  --file "${STALWART_DIR}/compose.local.yaml"

run_compose_config tls-mounted \
  --file "${STALWART_DIR}/compose.yaml" \
  --file "${STALWART_DIR}/compose.tls-mounted.yaml"

printf '==> API feature flags default-off regression\n'
uv run --project "${ROOT_DIR}/api" --frozen \
  pytest --quiet "${ROOT_DIR}/api/tests/test_feature_flags.py"

printf '==> Infra verification passed (no containers were started)\n'
