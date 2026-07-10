#!/usr/bin/env bash

# Shared, non-entry-point helpers for the transactional gVisor maintenance
# scripts. Entry points must enable `set -Eeuo pipefail` before sourcing this
# file.

readonly GVISOR_RELEASE_PIN="20260706.0"
readonly GVISOR_MIN_KERNEL="4.14.77"
readonly GVISOR_MIN_DOCKER="23.0.0"
readonly GVISOR_SMOKE_IMAGE="docker.io/library/hello-world@sha256:b44f8077f3cc983f21adf071c813599ff805af75196a456a326253c7b3357c48"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  return 1
}

init_host_paths() {
  local test_mode="${GVISOR_TEST_MODE:-0}"
  local canonical_test_root

  case "$test_mode" in
    0|1) ;;
    *) die "GVISOR_TEST_MODE must be exactly 0 or 1" ;;
  esac

  if [[ "$test_mode" == "1" ]]; then
    [[ -n "${GVISOR_TEST_ROOT:-}" ]] || die "GVISOR_TEST_ROOT is required in test mode"
    [[ "$GVISOR_TEST_ROOT" == /* ]] || die "GVISOR_TEST_ROOT must be absolute"
    [[ -d "$GVISOR_TEST_ROOT" ]] || die "GVISOR_TEST_ROOT must already exist"
    [[ ! -L "$GVISOR_TEST_ROOT" ]] || die "GVISOR_TEST_ROOT may not be a symlink"
    canonical_test_root="$(cd "$GVISOR_TEST_ROOT" && pwd -P)"
    [[ "$canonical_test_root" != "/" ]] || die "GVISOR_TEST_ROOT may not resolve to /"
    HOST_ROOT="${canonical_test_root%/}"
    STATE_OWNER_UID="$(id -u)"
    STATE_OWNER_GID="$(id -g)"
  else
    [[ -z "${GVISOR_TEST_ROOT+x}" ]] || die "GVISOR_TEST_ROOT is guarded by GVISOR_TEST_MODE=1"
    [[ -z "${GVISOR_TEST_TIMESTAMP+x}" ]] || die "GVISOR_TEST_TIMESTAMP is guarded by GVISOR_TEST_MODE=1"
    HOST_ROOT=""
    STATE_OWNER_UID="0"
    STATE_OWNER_GID="0"
  fi

  DAEMON_CONFIG="${HOST_ROOT}/etc/docker/daemon.json"
  RUNSC_PATH="${HOST_ROOT}/usr/local/bin/runsc"
  SHIM_PATH="${HOST_ROOT}/usr/local/bin/containerd-shim-runsc-v1"
  STATE_ROOT="${HOST_ROOT}/var/lib/gvisor-docker-install"
}

run_root() {
  if [[ "${GVISOR_TEST_MODE:-0}" == "1" ]]; then
    sudo "$@"
  else
    sudo -n "$@"
  fi
}

version_at_least() {
  local actual="$1"
  local minimum="$2"
  local actual_major actual_minor actual_patch
  local minimum_major minimum_minor minimum_patch

  [[ "$actual" =~ ^v?([0-9]+)\.([0-9]+)(\.([0-9]+))? ]] || return 1
  actual_major="${BASH_REMATCH[1]}"
  actual_minor="${BASH_REMATCH[2]}"
  actual_patch="${BASH_REMATCH[4]:-0}"
  [[ "$minimum" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || return 1
  minimum_major="${BASH_REMATCH[1]}"
  minimum_minor="${BASH_REMATCH[2]}"
  minimum_patch="${BASH_REMATCH[3]}"

  if (( 10#$actual_major != 10#$minimum_major )); then
    (( 10#$actual_major > 10#$minimum_major ))
    return
  fi
  if (( 10#$actual_minor != 10#$minimum_minor )); then
    (( 10#$actual_minor > 10#$minimum_minor ))
    return
  fi
  (( 10#$actual_patch >= 10#$minimum_patch ))
}

preflight_host() {
  local tool test_binary kernel docker_version docker_context docker_endpoint can_reload exec_start
  local -a required_tools=(cat chmod chown cp curl date dirname docker dockerd grep id install mkdir mktemp python3 rm sha512sum sudo systemctl test touch uname)

  for tool in "${required_tools[@]}"; do
    command -v "$tool" >/dev/null 2>&1 || die "required tool is missing: $tool"
  done
  test_binary="$(type -P test)"
  [[ -n "$test_binary" ]] || die "required external tool is missing: test"

  [[ "$(uname -s)" == "Linux" ]] || die "gVisor requires Linux"
  kernel="$(uname -r)"
  version_at_least "$kernel" "$GVISOR_MIN_KERNEL" || die "kernel $kernel is older than required $GVISOR_MIN_KERNEL"

  [[ -z "${DOCKER_HOST:-}" ]] || die "DOCKER_HOST must be unset; maintenance is restricted to the local Docker daemon"
  [[ -z "${DOCKER_CONTEXT:-}" ]] || die "DOCKER_CONTEXT must be unset; maintenance is restricted to the default local context"
  docker_context="$(docker context show)" || die "could not resolve the active Docker context"
  [[ "$docker_context" == "default" ]] || die "Docker context must be exactly default, not $docker_context"
  docker_endpoint="$(docker context inspect default --format '{{.Endpoints.docker.Host}}')" || \
    die "could not inspect the default Docker endpoint"
  [[ "$docker_endpoint" == "unix:///var/run/docker.sock" ]] || \
    die "Docker endpoint must be exactly unix:///var/run/docker.sock, not $docker_endpoint"

  if [[ "${GVISOR_TEST_MODE:-0}" != "1" ]]; then
    [[ -d /run/systemd/system ]] || die "systemd is not PID 1 on this host"
  fi
  systemctl is-active --quiet docker || die "Docker is not an active systemd service"
  can_reload="$(systemctl show docker -p CanReload --value)"
  [[ "$can_reload" == "yes" ]] || die "Docker's systemd unit does not support reload"
  exec_start="$(systemctl show docker -p ExecStart --value)"
  [[ "$exec_start" == *dockerd* ]] || die "Docker systemd ExecStart does not invoke dockerd"
  case " $exec_start " in
    *" --config-file"*|*" -c "*) die "Docker ExecStart has a conflicting config-file flag" ;;
  esac
  case " $exec_start " in
    *" --add-runtime"*) die "Docker ExecStart has a conflicting runtime flag" ;;
  esac
  case " $exec_start " in
    *" --default-runtime"*) die "Docker ExecStart changes the default runtime" ;;
  esac

  sudo -n true || die "passwordless non-interactive sudo is required for maintenance"
  docker_version="$(docker version --format '{{.Server.Version}}')"
  version_at_least "$docker_version" "$GVISOR_MIN_DOCKER" || die "Docker $docker_version is older than required $GVISOR_MIN_DOCKER"
  [[ -d "${HOST_ROOT}/etc/docker" ]] || die "Docker config directory is missing"
  [[ -d "${HOST_ROOT}/usr/local/bin" ]] || die "/usr/local/bin is missing"
  [[ -d "${HOST_ROOT}/var/lib" ]] || die "/var/lib is missing"
}

read_default_runtime() {
  local runtime
  runtime="$(docker info --format '{{.DefaultRuntime}}')"
  [[ -n "$runtime" ]] || { die "Docker returned an empty default runtime"; return 1; }
  printf '%s\n' "$runtime"
}

check_health_endpoints() {
  local contract_file="$1"
  local health_work_dir health_plan_file health_response_file
  local index probe_name endpoint response_type field expected_b64
  local count=0

  [[ -f "$contract_file" ]] || { die "health contract is missing: $contract_file"; return 1; }
  health_work_dir="$(mktemp -d)" || return 1
  health_plan_file="$health_work_dir/plan.tsv"

  if ! python3 - "$contract_file" > "$health_plan_file" <<'PY'
import base64
import json
import pathlib
import sys

contract_path = pathlib.Path(sys.argv[1])
with contract_path.open(encoding="utf-8") as handle:
    contract = json.load(handle)
if not isinstance(contract, list) or not contract:
    raise SystemExit("health contract must be a non-empty JSON array")

for index, item in enumerate(contract):
    if not isinstance(item, dict):
        raise SystemExit(f"health probe {index} must be an object")
    name = item.get("name")
    url = item.get("url")
    response = item.get("response")
    if not isinstance(name, str) or not name:
        raise SystemExit(f"health probe {index} requires a name")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise SystemExit(f"health probe {name!r} requires an HTTPS URL")
    if not isinstance(response, dict):
        raise SystemExit(f"health probe {name!r} requires a response contract")

    response_type = response.get("type")
    field = "-"
    if response_type == "json-field":
        field = response.get("field")
        expected = response.get("equals")
        if not isinstance(field, str) or not field or not isinstance(expected, str):
            raise SystemExit(f"health probe {name!r} has an invalid json-field contract")
    elif response_type == "contains":
        expected = response.get("value")
        if not isinstance(expected, str) or not expected:
            raise SystemExit(f"health probe {name!r} has an invalid contains contract")
    else:
        raise SystemExit(f"health probe {name!r} has unsupported response type")

    fields = (name, url, response_type, field)
    if any("\t" in value or "\n" in value for value in fields):
        raise SystemExit(f"health probe {name!r} contains unsupported control characters")
    encoded = base64.urlsafe_b64encode(expected.encode()).decode()
    print(index, name, url, response_type, field, encoded, sep="\t")
PY
  then
    rm -rf "$health_work_dir"
    die "health contract validation failed"
    return 1
  fi

  while IFS=$'\t' read -r index probe_name endpoint response_type field expected_b64; do
    [[ -n "$probe_name" ]] || continue
    health_response_file="$health_work_dir/$index.body"
    if ! curl --fail --silent --show-error --location --max-time 15 --output "$health_response_file" "$endpoint"; then
      rm -rf "$health_work_dir"
      die "health probe failed HTTP/TLS validation: $probe_name"
      return 1
    fi
    if ! python3 - "$health_response_file" "$response_type" "$field" "$expected_b64" <<'PY'
import base64
import json
import pathlib
import sys

body_path = pathlib.Path(sys.argv[1])
response_type = sys.argv[2]
field = sys.argv[3]
expected = base64.urlsafe_b64decode(sys.argv[4]).decode()
body = body_path.read_bytes()

if response_type == "contains":
    if expected.encode() not in body:
        raise SystemExit("required response marker is absent")
elif response_type == "json-field":
    value = json.loads(body)
    if not isinstance(value, dict) or value.get(field) != expected:
        raise SystemExit("required JSON field does not match")
else:
    raise SystemExit("unsupported response contract")
PY
    then
      rm -rf "$health_work_dir"
      die "health probe response contract failed: $probe_name"
      return 1
    fi
    ((count += 1))
  done < "$health_plan_file"

  rm -rf "$health_work_dir"
  (( count > 0 )) || die "health contract has no probes"
}

capture_workloads() {
  local output_dir="$1"
  local container_id state running health

  mkdir -p "$output_dir"
  docker ps --no-trunc --format '{{json .}}' > "$output_dir/containers.jsonl"
  docker ps -q --no-trunc > "$output_dir/container-ids.txt"
  : > "$output_dir/container-state.txt"
  while IFS= read -r container_id || [[ -n "$container_id" ]]; do
    [[ -n "$container_id" ]] || continue
    state="$(docker inspect --format '{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} {{.State.StartedAt}}' "$container_id")"
    read -r running health _ <<< "$state"
    [[ "$running" == "true" ]] || { die "existing container is not running: $container_id"; return 1; }
    [[ "$health" == "healthy" || "$health" == "none" ]] || { die "existing container is unhealthy: $container_id ($health)"; return 1; }
    printf '%s %s\n' "$container_id" "$state" >> "$output_dir/container-state.txt"
  done < "$output_dir/container-ids.txt"
}

verify_captured_workloads() (
  local state_dir="$1"
  local container_id state running health started_at
  local captured_id captured_running captured_health captured_started_at
  local found_capture
  local current_ids
  local verification_dir ids_copy state_copy

  run_root test -f "$state_dir/container-ids.before.txt" || { die "state is missing the captured container IDs"; return 1; }
  run_root test -f "$state_dir/container-state.before.txt" || { die "state is missing the captured container state"; return 1; }
  verification_dir="$(mktemp -d)" || return 1
  trap 'rm -rf "$verification_dir"' EXIT
  ids_copy="$verification_dir/container-ids.txt"
  state_copy="$verification_dir/container-state.txt"
  if ! run_root cat "$state_dir/container-ids.before.txt" > "$ids_copy" || \
     ! run_root cat "$state_dir/container-state.before.txt" > "$state_copy"; then
    return 1
  fi
  current_ids="$(docker ps -q --no-trunc)"
  docker ps --no-trunc --format '{{json .}}' >/dev/null
  while IFS= read -r container_id || [[ -n "$container_id" ]]; do
    [[ -n "$container_id" ]] || continue
    grep -Fqx "$container_id" <<< "$current_ids" || { die "existing container disappeared after maintenance: $container_id"; return 1; }
    state="$(docker inspect --format '{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} {{.State.StartedAt}}' "$container_id")"
    read -r running health started_at <<< "$state"
    [[ "$running" == "true" ]] || { die "existing container stopped during maintenance: $container_id"; return 1; }
    [[ "$health" == "healthy" || "$health" == "none" ]] || { die "existing container is unhealthy after maintenance: $container_id ($health)"; return 1; }
    found_capture=0
    while read -r captured_id captured_running captured_health captured_started_at; do
      if [[ "$captured_id" == "$container_id" ]]; then
        found_capture=1
        break
      fi
    done < "$state_copy"
    [[ "$found_capture" == "1" ]] || { die "state is missing the original details for container $container_id"; return 1; }
    [[ "$captured_running" == "true" && ( "$captured_health" == "healthy" || "$captured_health" == "none" ) ]] || { die "captured state for $container_id was not healthy"; return 1; }
    [[ "$started_at" == "$captured_started_at" ]] || { die "existing container restarted during maintenance: $container_id"; return 1; }
  done < "$ids_copy"
)

validate_docker_config() {
  local config="$1"
  dockerd --validate --config-file="$config"
}

verify_runsc_registration() {
  local runtime_path version first_line
  runtime_path="$(docker info --format '{{json .Runtimes}}' | python3 -c 'import json, sys; print(json.load(sys.stdin).get("runsc", {}).get("path", ""))')"
  [[ "$runtime_path" == "/usr/local/bin/runsc" ]] || { die "Docker runsc runtime path is not exactly /usr/local/bin/runsc"; return 1; }
  [[ -x "$RUNSC_PATH" ]] || { die "installed runsc is not executable at /usr/local/bin/runsc"; return 1; }
  [[ -x "$SHIM_PATH" ]] || { die "installed containerd shim is not executable"; return 1; }
  version="$("$RUNSC_PATH" --version)"
  first_line="${version%%$'\n'*}"
  [[ "$first_line" == "runsc version release-$GVISOR_RELEASE_PIN" ]] || { die "runsc version does not match pinned release $GVISOR_RELEASE_PIN: $first_line"; return 1; }
}

verify_default_runtime_unchanged() {
  local state_dir="$1"
  local expected actual
  expected="$(run_root cat "$state_dir/default-runtime.before")"
  actual="$(read_default_runtime)"
  [[ "$actual" == "$expected" ]] || { die "default runtime changed from $expected to $actual"; return 1; }
}

check_captured_health_endpoints() {
  local state_dir="$1"
  local contract_copy

  contract_copy="$(mktemp)" || return 1
  if ! run_root cat "$state_dir/health-contract.before.json" > "$contract_copy"; then
    rm -f "$contract_copy"
    return 1
  fi
  if check_health_endpoints "$contract_copy"; then
    rm -f "$contract_copy"
    return 0
  fi
  rm -f "$contract_copy"
  return 1
}

smoke_test_runsc() {
  local container_id runtime exit_code

  container_id="$(docker create --runtime=runsc --network=none "$GVISOR_SMOKE_IMAGE")"
  [[ -n "$container_id" ]] || { die "Docker did not return a smoke container ID"; return 1; }
  SMOKE_CONTAINER_ID="$container_id"
  runtime="$(docker inspect --format '{{.HostConfig.Runtime}}' "$container_id")"
  [[ "$runtime" == "runsc" ]] || { die "smoke container was not created with runsc"; return 1; }
  docker start --attach "$container_id" >/dev/null
  exit_code="$(docker inspect --format '{{.State.ExitCode}}' "$container_id")"
  [[ "$exit_code" == "0" ]] || { die "gVisor smoke container exited with $exit_code"; return 1; }
  docker rm "$container_id" >/dev/null
  SMOKE_CONTAINER_ID=""
}

cleanup_smoke_container() {
  if [[ -n "${SMOKE_CONTAINER_ID:-}" ]]; then
    docker rm --force "$SMOKE_CONTAINER_ID" >/dev/null 2>&1 || true
    SMOKE_CONTAINER_ID=""
  fi
}

classify_host_path() {
  local source="$1"
  local policy="$2"

  run_root python3 - "$source" "$policy" <<'PY'
import pathlib
import stat
import sys

path = pathlib.Path(sys.argv[1])
policy = sys.argv[2]
if policy not in {"regular", "file-or-symlink"}:
    raise SystemExit("invalid host-path classification policy")
try:
    metadata = path.lstat()
except FileNotFoundError:
    print("absent")
    raise SystemExit(0)
except OSError as exc:
    raise SystemExit(f"could not inspect protected host path {path}: {exc}")

mode = f"{stat.S_IMODE(metadata.st_mode):04o}"
if stat.S_ISREG(metadata.st_mode):
    print("regular", mode, metadata.st_uid, metadata.st_gid)
elif stat.S_ISLNK(metadata.st_mode) and policy == "file-or-symlink":
    print("symlink", mode, metadata.st_uid, metadata.st_gid)
elif stat.S_ISLNK(metadata.st_mode):
    raise SystemExit(f"protected host path may not be a symlink: {path}")
else:
    raise SystemExit(f"protected host path has an unsupported file type: {path}")
PY
}

backup_path() {
  local source="$1"
  local label="$2"
  local destination_name="$3"
  local state_dir="$4"
  local policy classification path_type

  if [[ "$label" == "daemon" ]]; then
    policy='regular'
  else
    policy='file-or-symlink'
  fi
  classification="$(classify_host_path "$source" "$policy")" || return 1
  path_type="${classification%% *}"
  if [[ "$path_type" == "regular" || "$path_type" == "symlink" ]]; then
    run_root cp -a "$source" "$state_dir/original/$destination_name"
    run_root touch "$state_dir/$label.present"
    run_root chmod 0400 "$state_dir/$label.present"
  elif [[ "$path_type" == "absent" ]]; then
    run_root touch "$state_dir/$label.absent"
    run_root chmod 0400 "$state_dir/$label.absent"
  else
    die "protected host path classification failed for $source"
    return 1
  fi
}

state_integrity() {
  local action="$1"
  local state_dir="$2"

  run_root python3 - "$action" "$state_dir" "$STATE_OWNER_UID" "$STATE_OWNER_GID" <<'PY'
import hashlib
import json
import os
import pathlib
import stat
import sys

action, raw_root, raw_uid, raw_gid = sys.argv[1:]
root = pathlib.Path(raw_root)
expected_uid = int(raw_uid)
expected_gid = int(raw_gid)
manifest_path = root / "integrity.json"


def inventory():
    records = []
    paths = sorted(
        (path for path in root.rglob("*") if path != manifest_path),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in paths:
        metadata = path.lstat()
        record = {
            "path": path.relative_to(root).as_posix(),
            "mode": stat.S_IMODE(metadata.st_mode),
            "uid": metadata.st_uid,
            "gid": metadata.st_gid,
        }
        if stat.S_ISREG(metadata.st_mode):
            digest = hashlib.sha512()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            record.update({"type": "file", "sha512": digest.hexdigest()})
        elif stat.S_ISDIR(metadata.st_mode):
            record["type"] = "directory"
        elif stat.S_ISLNK(metadata.st_mode):
            record.update({"type": "symlink", "target": os.readlink(path)})
        else:
            raise SystemExit(f"rollback state has unsupported file type: {path}")
        records.append(record)
    return records


if action == "write":
    if manifest_path.exists() or manifest_path.is_symlink():
        raise SystemExit("rollback state integrity manifest already exists")
    payload = {"schemaVersion": 1, "inventory": inventory()}
    temporary = root / ".integrity.json.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o400)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    os.chown(temporary, expected_uid, expected_gid)
    os.chmod(temporary, 0o400)
    os.replace(temporary, manifest_path)
elif action == "verify":
    metadata = manifest_path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o400:
        raise SystemExit("rollback state integrity manifest mode/type is invalid")
    if metadata.st_uid != expected_uid or metadata.st_gid != expected_gid:
        raise SystemExit("rollback state integrity manifest ownership is invalid")
    with manifest_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload != {"schemaVersion": 1, "inventory": inventory()}:
        raise SystemExit("rollback state integrity verification failed")
else:
    raise SystemExit("unsupported rollback state integrity action")
PY
}

create_state_backup() {
  local state_dir="$1"
  local snapshot_dir="$2"
  local health_contract_file="$3"

  local release_root="$STATE_ROOT/$GVISOR_RELEASE_PIN"
  local release_marker="$snapshot_dir/release"

  # Create root-owned 0700 parents and the timestamp directory without an
  # attacker-writable transition. Test mode uses the fixture owner because its
  # sudo shim deliberately never elevates.
  run_root python3 - "$STATE_ROOT" "$release_root" "$state_dir" \
    "$STATE_OWNER_UID" "$STATE_OWNER_GID" <<'PY'
import os
import pathlib
import stat
import sys

root, release_root, state_dir = map(pathlib.Path, sys.argv[1:4])
expected_uid = int(sys.argv[4])
expected_gid = int(sys.argv[5])

for directory in (root, release_root):
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError:
        metadata = directory.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise SystemExit(f"unsafe rollback state parent: {directory}")
        if metadata.st_uid != expected_uid or metadata.st_gid != expected_gid:
            raise SystemExit(f"rollback state parent has unexpected ownership: {directory}")
    os.chmod(directory, 0o700)
    os.chown(directory, expected_uid, expected_gid)

state_dir.mkdir(mode=0o700)
os.chmod(state_dir, 0o700)
os.chown(state_dir, expected_uid, expected_gid)
original = state_dir / "original"
original.mkdir(mode=0o700)
os.chmod(original, 0o700)
os.chown(original, expected_uid, expected_gid)
PY
  backup_path "$DAEMON_CONFIG" daemon daemon.json "$state_dir"
  backup_path "$RUNSC_PATH" runsc runsc "$state_dir"
  backup_path "$SHIM_PATH" shim containerd-shim-runsc-v1 "$state_dir"
  (umask 077; printf '%s\n' "$GVISOR_RELEASE_PIN" > "$release_marker")
  run_root install -m 0400 "$release_marker" "$state_dir/release"
  run_root install -m 0400 "$snapshot_dir/default-runtime.before" "$state_dir/default-runtime.before"
  run_root install -m 0400 "$snapshot_dir/container-ids.txt" "$state_dir/container-ids.before.txt"
  run_root install -m 0400 "$snapshot_dir/containers.jsonl" "$state_dir/containers.before.jsonl"
  run_root install -m 0400 "$snapshot_dir/container-state.txt" "$state_dir/container-state.before.txt"
  run_root install -m 0400 "$health_contract_file" "$state_dir/health-contract.before.json"
  state_integrity write "$state_dir"
  state_integrity verify "$state_dir"
}

sentinel_state() {
  local state_dir="$1"
  local label="$2"
  local present="$state_dir/$label.present"
  local absent="$state_dir/$label.absent"

  if run_root test -f "$present" && ! run_root test -e "$absent"; then
    printf '%s\n' present
  elif run_root test -f "$absent" && ! run_root test -e "$present"; then
    printf '%s\n' absent
  else
    die "state must contain exactly one $label present/absent sentinel"
  fi
}

validate_state_dir() {
  local requested="$1"
  local canonical_state

  canonical_state="$(run_root python3 - "$STATE_ROOT" "$requested" \
    "$GVISOR_RELEASE_PIN" "$STATE_OWNER_UID" "$STATE_OWNER_GID" <<'PY'
import pathlib
import re
import stat
import sys

raw_root, raw_state, release, raw_uid, raw_gid = sys.argv[1:]
expected_uid = int(raw_uid)
expected_gid = int(raw_gid)
root = pathlib.Path(raw_root).resolve(strict=True)
requested = pathlib.Path(raw_state)
if requested.is_symlink():
    raise SystemExit("state directory may not be a symlink")
state = requested.resolve(strict=True)
release_root = (root / release).resolve(strict=True)
if state.parent != release_root or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", state.name):
    raise SystemExit("state directory is outside the pinned release state root")
for directory in (root, release_root, state, state / "original"):
    metadata = directory.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise SystemExit(f"rollback state directory is unsafe: {directory}")
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise SystemExit(f"rollback state directory mode is not 0700: {directory}")
    if metadata.st_uid != expected_uid or metadata.st_gid != expected_gid:
        raise SystemExit(f"rollback state directory ownership is invalid: {directory}")

def require_regular(path: pathlib.Path) -> None:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise SystemExit(f"rollback state file is missing or unsafe: {path}")

release_marker = state / "release"
require_regular(release_marker)
if release_marker.read_text(encoding="utf-8").strip() != release:
    raise SystemExit("state release does not match the pinned release")
for label in ("daemon", "runsc", "shim"):
    sentinels = [state / f"{label}.present", state / f"{label}.absent"]
    if sum(path.exists() and stat.S_ISREG(path.lstat().st_mode) for path in sentinels) != 1:
        raise SystemExit(f"state must contain exactly one {label} present/absent sentinel")
for name in (
    "default-runtime.before",
    "container-ids.before.txt",
    "container-state.before.txt",
    "containers.before.jsonl",
    "health-contract.before.json",
    "integrity.json",
):
    require_regular(state / name)
print(state)
PY
)" || { die "rollback state validation failed"; return 1; }
  state_integrity verify "$canonical_state" || { die "rollback state integrity validation failed"; return 1; }
  printf '%s\n' "$canonical_state"
}

restore_one_path() {
  local state_dir="$1"
  local label="$2"
  local backup_name="$3"
  local target="$4"
  local state

  state="$(sentinel_state "$state_dir" "$label")" || return 1
  if [[ "$state" == "present" ]]; then
    if ! run_root test -f "$state_dir/original/$backup_name" && \
       ! run_root test -L "$state_dir/original/$backup_name"; then
      return 1
    fi
    run_root rm -f "$target" || return 1
    run_root cp -a "$state_dir/original/$backup_name" "$target" || return 1
  else
    run_root rm -f "$target" || return 1
  fi
}

restore_state() {
  local state_dir="$1"
  local work_dir="$2"
  local daemon_state rollback_candidate

  state_integrity verify "$state_dir" || return 1
  daemon_state="$(sentinel_state "$state_dir" daemon)" || return 1
  rollback_candidate="$work_dir/daemon.rollback.json"
  if [[ "$daemon_state" == "present" ]]; then
    run_root cat "$state_dir/original/daemon.json" > "$rollback_candidate" || return 1
  else
    printf '{}\n' > "$rollback_candidate" || return 1
  fi

  # Validate the configuration that rollback will restore before touching the
  # live daemon configuration.
  validate_docker_config "$rollback_candidate" || return 1
  restore_one_path "$state_dir" daemon daemon.json "$DAEMON_CONFIG" || return 1
  restore_one_path "$state_dir" runsc runsc "$RUNSC_PATH" || return 1
  restore_one_path "$state_dir" shim containerd-shim-runsc-v1 "$SHIM_PATH" || return 1
  # The installed bytes are identical to the already validated rollback
  # candidate. Do not re-open a restored root-only daemon.json as the
  # unprivileged maintenance user.
  run_root systemctl reload docker || return 1
  verify_default_runtime_unchanged "$state_dir" || return 1
  verify_captured_workloads "$state_dir" || return 1
  check_captured_health_endpoints "$state_dir" || return 1
}
