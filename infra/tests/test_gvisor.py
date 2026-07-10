from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GVISOR = ROOT / "infra" / "gvisor"
INSTALL = GVISOR / "install.sh"
ROLLBACK = GVISOR / "rollback.sh"
SMOKE_IMAGE = (
    "docker.io/library/hello-world@"
    "sha256:b44f8077f3cc983f21adf071c813599ff805af75196a456a326253c7b3357c48"
)


@dataclass
class Harness:
    root: Path
    log: Path
    env: dict[str, str]

    @property
    def daemon(self) -> Path:
        return self.root / "etc" / "docker" / "daemon.json"

    @property
    def runsc(self) -> Path:
        return self.root / "usr" / "local" / "bin" / "runsc"

    @property
    def shim(self) -> Path:
        return self.root / "usr" / "local" / "bin" / "containerd-shim-runsc-v1"

    @property
    def state_root(self) -> Path:
        return self.root / "var" / "lib" / "gvisor-docker-install"

    def run(
        self,
        script: Path,
        *arguments: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = self.env.copy()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [str(script), *arguments],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


def _write_dispatcher(fake_bin: Path) -> None:
    dispatcher = fake_bin / "mock-command"
    dispatcher.write_text(
        r'''#!/usr/bin/env bash
set -euo pipefail
command_name="$(basename "$0")"
printf '%s' "$command_name" >> "${MOCK_LOG:?}"
printf ' %q' "$@" >> "$MOCK_LOG"
printf '\n' >> "$MOCK_LOG"

case "$command_name" in
  uname)
    case "${1:-}" in
      -s) printf '%s\n' "${MOCK_UNAME_S:-Linux}" ;;
      -m) printf '%s\n' "${MOCK_UNAME_M:-x86_64}" ;;
      -r) printf '%s\n' "${MOCK_UNAME_R:-6.8.0}" ;;
      *) printf '%s\n' Linux ;;
    esac
    ;;
  sudo)
    if [[ "${1:-}" == "-n" && "${2:-}" == "true" ]]; then
      exit "${MOCK_SUDO_FAIL:-0}"
    fi
    for argument in "$@"; do
      case "$argument" in
        /etc/*|/usr/local/*|/var/lib/*)
          printf 'mock sudo denied real host path: %s\n' "$argument" >&2
          exit 97
          ;;
      esac
    done
    if [[ "${MOCK_FAIL_RUNSC_INSTALL:-0}" == "1" && \
          " $* " == *" install "* && \
          " $* " == *" ${GVISOR_TEST_ROOT}/usr/local/bin/runsc "* ]]; then
      exit 73
    fi
    if [[ "${MOCK_SIGNAL_RUNSC_INSTALL:-}" != "" && \
          " $* " == *" install "* && \
          " $* " == *" ${GVISOR_TEST_ROOT}/usr/local/bin/runsc "* ]]; then
      "$@"
      kill -s "$MOCK_SIGNAL_RUNSC_INSTALL" "$PPID"
      exit 0
    fi
    exec "$@"
    ;;
  systemctl)
    case "${1:-}" in
      restart|stop|start|daemon-reload)
        printf '%s\n' "DENIED_DESTRUCTIVE systemctl $*" >> "${MOCK_LOG:?}"
        exit 99
        ;;
    esac
    if [[ "${1:-}" == "is-active" ]]; then
      exit "${MOCK_DOCKER_INACTIVE:-0}"
    fi
    if [[ "${1:-}" == "show" && "$*" == *"CanReload"* ]]; then
      printf '%s\n' "${MOCK_CAN_RELOAD:-yes}"
      exit 0
    fi
    if [[ "${1:-}" == "show" && "$*" == *"ExecStart"* ]]; then
      printf '%s\n' "${MOCK_EXEC_START:-/usr/bin/dockerd -H fd://}"
      exit 0
    fi
    if [[ "${1:-}" == "reload" ]]; then
      if [[ "${MOCK_RELOAD_FAIL_ONCE:-0}" == "1" && ! -e "${MOCK_RELOAD_MARKER}.failed" ]]; then
        : > "${MOCK_RELOAD_MARKER}.failed"
        exit 1
      fi
      : > "${MOCK_RELOAD_MARKER}"
      exit 0
    fi
    ;;
  curl)
    output=""
    previous=""
    for argument in "$@"; do
      if [[ "$previous" == "--output" || "$previous" == "-o" ]]; then
        output="$argument"
      fi
      previous="$argument"
    done
    if [[ -n "$output" && "$output" != "/dev/null" ]]; then
      if [[ "$(basename "$output")" == "runsc" ]]; then
        printf '%s\n' '#!/usr/bin/env sh' 'printf "%s\\n" "runsc version ${MOCK_RUNSC_VERSION:-release-20260706.0}"' > "$output"
      elif [[ "$*" == *"api.kiaparsaprintingmoneymachine.cloud/"* ]]; then
        if [[ "${MOCK_HEALTH_BODY_FAIL_AFTER_MUTATION:-0}" == "1" ]] && \
           grep -q '"runsc"' "${GVISOR_TEST_ROOT}/etc/docker/daemon.json" 2>/dev/null; then
          printf '%s\n' '{"name":"wrong-service"}' > "$output"
        else
          printf '%s\n' '{"name":"Trading Dashboard API","version":"0.1.0"}' > "$output"
        fi
      elif [[ "$*" == *"dashboard.kiaparsaprintingmoneymachine.cloud/"* ]]; then
        if [[ "${MOCK_HEALTH_BODY_FAIL_AFTER_MUTATION:-0}" == "1" ]] && \
           grep -q '"runsc"' "${GVISOR_TEST_ROOT}/etc/docker/daemon.json" 2>/dev/null; then
          printf '%s\n' 'wrong dashboard body' > "$output"
        else
          printf '%s\n' '<!doctype html><html><head><title>Signal Copier | Dashboard</title></head></html>' > "$output"
        fi
      else
        printf '%s\n' "downloaded-$output" > "$output"
      fi
    fi
    exit "${MOCK_HEALTH_FAIL:-0}"
    ;;
  sha512sum)
    exit "${MOCK_CHECKSUM_FAIL:-0}"
    ;;
  dockerd)
    if [[ "${MOCK_VALIDATE_FAIL:-0}" == "1" ]]; then
      exit 1
    fi
    config=""
    for argument in "$@"; do
      case "$argument" in
        --config-file=*) config="${argument#*=}" ;;
      esac
    done
    python3 -c 'import json,sys; json.load(open(sys.argv[1], encoding="utf-8"))' "$config"
    ;;
  docker)
    case "${1:-}" in
      stop|restart|kill)
        printf '%s\n' "DENIED_DESTRUCTIVE docker $*" >> "${MOCK_LOG:?}"
        exit 99
        ;;
    esac
    if [[ "${1:-}" == "context" && "${2:-}" == "show" ]]; then
      printf '%s\n' "${MOCK_DOCKER_CONTEXT:-default}"
      exit 0
    fi
    if [[ "${1:-}" == "context" && "${2:-}" == "inspect" ]]; then
      printf '%s\n' "${MOCK_DOCKER_ENDPOINT:-unix:///var/run/docker.sock}"
      exit 0
    fi
    if [[ "${1:-}" == "version" ]]; then
      printf '%s\n' "${MOCK_DOCKER_VERSION:-28.1.0}"
      exit 0
    fi
    if [[ "${1:-}" == "info" ]]; then
      if [[ "$*" == *"DefaultRuntime"* ]]; then
        if [[ "${MOCK_MUTATED_DEFAULT_RUNTIME:-}" != "" ]] && \
           grep -q '"runsc"' "${GVISOR_TEST_ROOT}/etc/docker/daemon.json" 2>/dev/null; then
          printf '%s\n' "$MOCK_MUTATED_DEFAULT_RUNTIME"
        else
          printf '%s\n' "${MOCK_DEFAULT_RUNTIME:-runc}"
        fi
      elif [[ "$*" == *"Runtimes"* ]]; then
        printf '%s\n' '{"runc":{"path":"runc"},"runsc":{"path":"/usr/local/bin/runsc"}}'
      else
        printf '%s\n' '{}'
      fi
      exit 0
    fi
    if [[ "${1:-}" == "ps" && " $* " == *" -q "* ]]; then
      printf '%s\n' abc123
      exit 0
    fi
    if [[ "${1:-}" == "ps" ]]; then
      printf '%s\n' '{"ID":"abc123","Names":"existing","State":"running","Status":"Up","Health":"healthy"}'
      exit 0
    fi
    if [[ "${1:-}" == "inspect" && "$*" == *"HostConfig.Runtime"* ]]; then
      printf '%s\n' runsc
      exit 0
    fi
    if [[ "${1:-}" == "inspect" && "$*" == *"State.ExitCode"* ]]; then
      printf '%s\n' 0
      exit 0
    fi
    if [[ "${1:-}" == "inspect" && "$*" == *"State.Running"* ]]; then
      if grep -q '"runsc"' "${GVISOR_TEST_ROOT}/etc/docker/daemon.json" 2>/dev/null; then
        printf '%s %s %s\n' \
          "${MOCK_POST_RUNNING:-true}" \
          "${MOCK_POST_HEALTH:-healthy}" \
          "${MOCK_POST_STARTED_AT:-2026-07-10T00:00:00Z}"
      else
        printf '%s\n' 'true healthy 2026-07-10T00:00:00Z'
      fi
      exit 0
    fi
    if [[ "${1:-}" == "create" ]]; then
      [[ " $* " == *" ${MOCK_SMOKE_IMAGE:?} "* ]]
      printf '%s\n' smoke-container
      exit 0
    fi
    if [[ "${1:-}" == "rm" ]]; then
      [[ " $* " == *" smoke-container "* ]] || {
        printf '%s\n' "DENIED_DESTRUCTIVE docker $*" >> "${MOCK_LOG:?}"
        exit 99
      }
      exit "${MOCK_SMOKE_FAIL:-0}"
    fi
    if [[ "${1:-}" == "start" ]]; then
      exit "${MOCK_SMOKE_FAIL:-0}"
    fi
    ;;
  jq)
    exec python3 "${MOCK_JQ:?}" "$@"
    ;;
esac
''',
        encoding="utf-8",
    )
    dispatcher.chmod(dispatcher.stat().st_mode | stat.S_IXUSR)
    for name in [
        "curl",
        "docker",
        "dockerd",
        "jq",
        "sha512sum",
        "sudo",
        "systemctl",
        "uname",
    ]:
        (fake_bin / name).symlink_to(dispatcher.name)


def _write_mock_jq(path: Path) -> None:
    path.write_text(
        """from __future__ import annotations
import json
import sys

args = sys.argv[1:]
raw = "-r" in args
data = json.load(sys.stdin)
program = next((arg for arg in args if not arg.startswith("-")), ".")
if "DefaultRuntime" in program:
    value = data.get("DefaultRuntime", "runc")
elif "Runtimes" in program:
    value = data.get("Runtimes", {}).get("runsc", {}).get("path", "")
else:
    value = data
if raw and isinstance(value, str):
    print(value)
else:
    print(json.dumps(value))
""",
        encoding="utf-8",
    )


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    root = tmp_path / "host"
    (root / "etc" / "docker").mkdir(parents=True)
    (root / "usr" / "local" / "bin").mkdir(parents=True)
    (root / "var" / "lib").mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_dispatcher(fake_bin)
    mock_jq = tmp_path / "mock_jq.py"
    _write_mock_jq(mock_jq)
    log = tmp_path / "commands.log"
    reload_marker = tmp_path / "reloaded"
    path_tail = os.environ.get("PATH", "/usr/bin:/bin")
    env = os.environ.copy()
    env.pop("DOCKER_HOST", None)
    env.pop("DOCKER_CONTEXT", None)
    env.update(
        {
            "DRY_RUN": "0",
            "GVISOR_TEST_MODE": "1",
            "GVISOR_TEST_ROOT": str(root),
            "GVISOR_TEST_TIMESTAMP": "20260710T000000Z",
            "MOCK_JQ": str(mock_jq),
            "MOCK_LOG": str(log),
            "MOCK_RELOAD_MARKER": str(reload_marker),
            "MOCK_SMOKE_IMAGE": SMOKE_IMAGE,
            "PATH": f"{fake_bin}:{path_tail}",
        }
    )
    return Harness(root=root, log=log, env=env)


def command_lines(harness: Harness) -> list[str]:
    if not harness.log.exists():
        return []
    return harness.log.read_text(encoding="utf-8").splitlines()


def test_release_is_exact_and_cannot_be_overridden(harness: Harness) -> None:
    result = harness.run(
        INSTALL,
        extra_env={"DRY_RUN": "1", "GVISOR_RELEASE": "latest"},
    )

    assert result.returncode != 0
    assert "override" in result.stderr.lower()
    common = (GVISOR / "common.sh").read_text(encoding="utf-8")
    release_assignment = re.fullmatch(
        r'readonly GVISOR_RELEASE_PIN="([0-9]{8}\.[0-9]+)"',
        next(
            line
            for line in common.splitlines()
            if line.startswith("readonly GVISOR_RELEASE_PIN=")
        ),
    )
    assert release_assignment is not None
    assert release_assignment.group(1) == "20260706.0"


def test_release_checksums_are_embedded_for_both_supported_architectures() -> None:
    source = INSTALL.read_text(encoding="utf-8")
    expected = {
        "x86_64": {
            "runsc_sha512": "73938c145ebe554cf61a01da455688f4b732eebdf7b1b635bdef5b195868b363d8cb400e3d92ed1f377b78996805556c247a4849583910cb04e92b156053033e",
            "shim_sha512": "6f1b34266ed3ab503f6e88116dd97d0fb5f79311ea174059dd284de11b36ee062649da2fe3dccea9e2d25abe4df04bee5ee443ec0b9348ae44e63fabda28e8f8",
        },
        "aarch64|arm64": {
            "runsc_sha512": "a4962fe56ee62c841c270443a3617b6626db3fb282e65793f6762df78b3209304dfe2e094e524b3d2b4c781c05b1b95744ce9fe50b49edee43090b27c2956c4b",
            "shim_sha512": "2ddb4eacc5a30e2aadf882b6dfa86b579ce46861f0cd13bc415c18b88d9c4d8309ec0bc7ddfe741b2fb5747af6c9f2f736e2169c1a46fb6f1a227f4b8962a88b",
        },
    }
    parsed: dict[str, dict[str, str]] = {}
    for architecture in expected:
        block = re.search(
            rf"^  {re.escape(architecture)}\)\n(?P<body>.*?)^    ;;$",
            source,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert block is not None
        parsed[architecture] = dict(
            re.findall(
                r'^    (runsc_sha512|shim_sha512)="([0-9a-f]{128})"$',
                block.group("body"),
                flags=re.MULTILINE,
            )
        )
    assert parsed == expected


def test_health_contract_uses_public_typed_liveness_probes() -> None:
    contract = json.loads((GVISOR / "health-contract.json").read_text(encoding="utf-8"))

    assert contract == [
        {
            "name": "api-liveness",
            "url": "https://api.kiaparsaprintingmoneymachine.cloud/",
            "response": {
                "type": "json-field",
                "field": "name",
                "equals": "Trading Dashboard API",
            },
        },
        {
            "name": "dashboard-liveness",
            "url": "https://dashboard.kiaparsaprintingmoneymachine.cloud/",
            "response": {"type": "contains", "value": "Signal Copier"},
        },
    ]
    assert all("/api/health" not in item["url"] for item in contract)


@pytest.mark.parametrize("value", ["", "true", "yes", "2", "01"])
def test_dry_run_parser_rejects_every_value_except_zero_or_one(
    harness: Harness, value: str
) -> None:
    result = harness.run(INSTALL, extra_env={"DRY_RUN": value})

    assert result.returncode != 0
    assert "dry_run" in result.stderr.lower()
    assert command_lines(harness) == []


def test_install_denies_unconfirmed_maintenance_without_commands(harness: Harness) -> None:
    result = harness.run(INSTALL)

    assert result.returncode != 0
    assert "--confirm-maintenance" in result.stderr
    assert command_lines(harness) == []
    assert not harness.state_root.exists()


def test_dry_run_is_truthful_and_performs_no_mutation(harness: Harness) -> None:
    result = harness.run(INSTALL, extra_env={"DRY_RUN": "1"})

    assert result.returncode == 0, result.stderr
    assert "would" in result.stdout.lower()
    assert "no changes were made" in result.stdout.lower()
    assert "installed" not in result.stdout.lower()
    calls = command_lines(harness)
    assert not any(line.startswith("sudo ") for line in calls)
    assert not any(line.startswith("curl ") for line in calls)
    assert not any("systemctl reload" in line for line in calls)
    assert not harness.state_root.exists()


@pytest.mark.parametrize("value", ["", "true", "yes", "2", "01"])
def test_rollback_dry_run_parser_rejects_every_value_except_zero_or_one(
    harness: Harness, value: str
) -> None:
    result = harness.run(
        ROLLBACK,
        "--state-dir",
        "/var/lib/gvisor-docker-install/20260706.0/example",
        extra_env={"DRY_RUN": value},
    )

    assert result.returncode != 0
    assert "dry_run" in result.stderr.lower()
    assert command_lines(harness) == []


def test_rollback_dry_run_is_truthful_and_performs_no_mutation(harness: Harness) -> None:
    result = harness.run(
        ROLLBACK,
        "--state-dir",
        "/var/lib/gvisor-docker-install/20260706.0/example",
        extra_env={"DRY_RUN": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "would" in result.stdout.lower()
    assert "no changes were made" in result.stdout.lower()
    assert "restored" not in result.stdout.lower()
    assert command_lines(harness) == []
    assert not harness.state_root.exists()


def test_checksum_failure_happens_before_backup_or_mutation(harness: Harness) -> None:
    result = harness.run(
        INSTALL,
        "--confirm-maintenance",
        extra_env={"MOCK_CHECKSUM_FAIL": "1"},
    )

    assert result.returncode != 0
    calls = command_lines(harness)
    assert any(line.startswith("sha512sum ") for line in calls)
    assert not any("systemctl reload" in line for line in calls)
    assert not any(" install " in f" {line} " for line in calls if line.startswith("sudo "))
    assert not harness.state_root.exists()
    assert not harness.daemon.exists()


def test_absent_files_get_sentinels_and_exact_runtime_path(harness: Harness) -> None:
    result = harness.run(INSTALL, "--confirm-maintenance")

    assert result.returncode == 0, result.stderr
    state_dirs = list(harness.state_root.glob("20260706.0/*"))
    assert len(state_dirs) == 1
    state = state_dirs[0]
    assert (state / "daemon.absent").is_file()
    assert (state / "runsc.absent").is_file()
    assert (state / "shim.absent").is_file()
    daemon = json.loads(harness.daemon.read_text(encoding="utf-8"))
    assert daemon["runtimes"]["runsc"] == {"path": "/usr/local/bin/runsc"}
    assert "default-runtime" not in daemon
    assert stat.S_IMODE(harness.daemon.stat().st_mode) == 0o600
    assert harness.runsc.is_file()
    assert harness.shim.is_file()
    assert any(
        line.startswith("sudo python3 - ") and str(harness.daemon) in line
        for line in command_lines(harness)
    )


def test_existing_config_and_binaries_are_preserved_with_modes(harness: Harness) -> None:
    harness.daemon.write_text('{"default-runtime":"runc","log-level":"warn"}\n', encoding="utf-8")
    harness.daemon.chmod(0o600)
    harness.runsc.write_bytes(b"old-runsc")
    harness.shim.write_bytes(b"old-shim")
    harness.runsc.chmod(0o751)
    harness.shim.chmod(0o711)

    result = harness.run(INSTALL, "--confirm-maintenance")

    assert result.returncode == 0, result.stderr
    state = next((harness.state_root / "20260706.0").iterdir())
    assert (state / "daemon.present").is_file()
    assert (state / "runsc.present").is_file()
    assert (state / "shim.present").is_file()
    assert (state / "original" / "daemon.json").read_text(encoding="utf-8") == (
        '{"default-runtime":"runc","log-level":"warn"}\n'
    )
    assert (state / "original" / "runsc").read_bytes() == b"old-runsc"
    assert stat.S_IMODE((state / "original" / "runsc").stat().st_mode) == 0o751
    assert (state / "original" / "containerd-shim-runsc-v1").read_bytes() == b"old-shim"
    assert stat.S_IMODE(
        (state / "original" / "containerd-shim-runsc-v1").stat().st_mode
    ) == 0o711
    assert stat.S_IMODE(harness.daemon.stat().st_mode) == 0o600
    assert stat.S_IMODE(state.stat().st_mode) == 0o700
    assert (state / "integrity.json").is_file()
    assert stat.S_IMODE((state / "integrity.json").stat().st_mode) == 0o400
    assert not any(line.startswith("sudo chown ") for line in command_lines(harness))
    assert any(
        line.startswith("sudo python3 - ") and str(harness.daemon) in line
        for line in command_lines(harness)
    )


def test_post_backup_binary_install_failure_triggers_automatic_rollback(
    harness: Harness,
) -> None:
    result = harness.run(
        INSTALL,
        "--confirm-maintenance",
        extra_env={"MOCK_FAIL_RUNSC_INSTALL": "1"},
    )

    assert result.returncode != 0
    assert "automatic rollback" in (result.stdout + result.stderr).lower()
    assert not harness.daemon.exists()
    assert not harness.runsc.exists()
    assert not harness.shim.exists()
    assert any("systemctl reload" in line for line in command_lines(harness))


def test_sigterm_after_mutation_triggers_automatic_rollback(harness: Harness) -> None:
    result = harness.run(
        INSTALL,
        "--confirm-maintenance",
        extra_env={"MOCK_SIGNAL_RUNSC_INSTALL": "TERM"},
    )

    assert result.returncode == 143
    assert "signal term" in (result.stdout + result.stderr).lower()
    assert "automatic rollback" in (result.stdout + result.stderr).lower()
    assert not harness.daemon.exists()
    assert not harness.runsc.exists()
    assert not harness.shim.exists()
    assert any("systemctl reload" in line for line in command_lines(harness))


def test_candidate_and_installed_config_are_validated_before_reload(harness: Harness) -> None:
    result = harness.run(INSTALL, "--confirm-maintenance")

    assert result.returncode == 0, result.stderr
    calls = command_lines(harness)
    validate_indexes = [index for index, line in enumerate(calls) if line.startswith("dockerd ")]
    config_install_index = next(
        index
        for index, line in enumerate(calls)
        if line.startswith("sudo install ") and "daemon.json" in line
    )
    reload_index = next(index for index, line in enumerate(calls) if "systemctl reload" in line)
    assert len(validate_indexes) >= 2
    assert validate_indexes[0] < config_install_index < validate_indexes[1] < reload_index
    privileged_validation_index = next(
        index
        for index, line in enumerate(calls)
        if line.startswith("sudo dockerd ") and str(harness.daemon) in line
    )
    assert config_install_index < privileged_validation_index < reload_index


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"MOCK_UNAME_S": "Darwin"}, "linux"),
        ({"MOCK_UNAME_R": "4.14.76"}, "kernel"),
        ({"MOCK_DOCKER_VERSION": "22.99.0"}, "docker"),
        ({"DOCKER_HOST": "tcp://remote.example:2376"}, "docker_host"),
        ({"DOCKER_CONTEXT": "remote-production"}, "docker_context"),
        ({"MOCK_DOCKER_CONTEXT": "remote-production"}, "context"),
        ({"MOCK_DOCKER_ENDPOINT": "ssh://operator@remote.example"}, "endpoint"),
        ({"MOCK_CAN_RELOAD": "no"}, "reload"),
        ({"MOCK_SUDO_FAIL": "1"}, "sudo"),
        ({"MOCK_EXEC_START": "/usr/bin/dockerd --config-file=/tmp/other.json"}, "config"),
        ({"MOCK_EXEC_START": "/usr/bin/dockerd --add-runtime bad=/tmp/bad"}, "runtime"),
        ({"MOCK_EXEC_START": "/usr/bin/dockerd --default-runtime=runsc"}, "default"),
    ],
)
def test_preflight_rejects_unsupported_or_conflicting_hosts_before_mutation(
    harness: Harness, environment: dict[str, str], message: str
) -> None:
    result = harness.run(INSTALL, "--confirm-maintenance", extra_env=environment)

    assert result.returncode != 0
    assert message in result.stderr.lower()
    assert not harness.state_root.exists()
    assert not any("systemctl reload" in line for line in command_lines(harness))


def test_default_runtime_change_triggers_automatic_rollback(harness: Harness) -> None:
    result = harness.run(
        INSTALL,
        "--confirm-maintenance",
        extra_env={"MOCK_MUTATED_DEFAULT_RUNTIME": "crun"},
    )

    assert result.returncode != 0
    assert "automatic rollback" in (result.stdout + result.stderr).lower()
    assert not harness.daemon.exists()
    assert not harness.runsc.exists()
    assert not harness.shim.exists()
    calls = command_lines(harness)
    assert sum("systemctl reload" in line for line in calls) >= 2
    rollback_validate = max(index for index, line in enumerate(calls) if line.startswith("dockerd "))
    final_reload = max(index for index, line in enumerate(calls) if "systemctl reload" in line)
    assert rollback_validate < final_reload


def test_reload_failure_triggers_automatic_rollback(harness: Harness) -> None:
    result = harness.run(
        INSTALL,
        "--confirm-maintenance",
        extra_env={"MOCK_RELOAD_FAIL_ONCE": "1"},
    )

    assert result.returncode != 0
    assert not harness.daemon.exists()
    assert not harness.runsc.exists()
    assert not harness.shim.exists()
    assert sum("systemctl reload" in line for line in command_lines(harness)) >= 2


def test_manual_rollback_requires_confirmation_and_restores_originals(harness: Harness) -> None:
    harness.daemon.write_text('{"log-driver":"local"}\n', encoding="utf-8")
    harness.daemon.chmod(0o600)
    harness.runsc.write_bytes(b"old-runsc")
    harness.shim.write_bytes(b"old-shim")
    assert harness.run(INSTALL, "--confirm-maintenance").returncode == 0
    state = next((harness.state_root / "20260706.0").iterdir())
    harness.log.write_text("", encoding="utf-8")

    denied = harness.run(ROLLBACK, "--state-dir", str(state))
    assert denied.returncode != 0
    assert "--confirm-maintenance" in denied.stderr
    assert command_lines(harness) == []

    restored = harness.run(
        ROLLBACK,
        "--confirm-maintenance",
        "--state-dir",
        str(state),
    )
    assert restored.returncode == 0, restored.stderr
    assert harness.daemon.read_text(encoding="utf-8") == '{"log-driver":"local"}\n'
    assert stat.S_IMODE(harness.daemon.stat().st_mode) == 0o600
    assert harness.runsc.read_bytes() == b"old-runsc"
    assert harness.shim.read_bytes() == b"old-shim"
    calls = command_lines(harness)
    validate_index = next(index for index, line in enumerate(calls) if line.startswith("dockerd "))
    reload_index = next(index for index, line in enumerate(calls) if "systemctl reload" in line)
    assert validate_index < reload_index


def test_manual_rollback_rejects_tampered_root_state_before_mutation(
    harness: Harness,
) -> None:
    harness.daemon.write_text('{"log-driver":"local"}\n', encoding="utf-8")
    installed = harness.run(INSTALL, "--confirm-maintenance")
    assert installed.returncode == 0, installed.stderr
    state = next((harness.state_root / "20260706.0").iterdir())
    (state / "original" / "daemon.json").write_text(
        '{"default-runtime":"runsc"}\n', encoding="utf-8"
    )
    harness.log.write_text("", encoding="utf-8")

    rejected = harness.run(
        ROLLBACK,
        "--confirm-maintenance",
        "--state-dir",
        str(state),
    )

    assert rejected.returncode != 0
    assert "integrity" in rejected.stderr.lower()
    assert json.loads(harness.daemon.read_text(encoding="utf-8"))["runtimes"][
        "runsc"
    ] == {"path": "/usr/local/bin/runsc"}
    assert not any("systemctl reload" in line for line in command_lines(harness))


def test_prior_binary_symlinks_are_preserved_and_restored(harness: Harness) -> None:
    prior_runsc = harness.root / "prior-runsc"
    prior_shim = harness.root / "prior-shim"
    prior_runsc.write_bytes(b"prior-runsc-target")
    prior_shim.write_bytes(b"prior-shim-target")
    harness.runsc.symlink_to(os.path.relpath(prior_runsc, harness.runsc.parent))
    harness.shim.symlink_to(os.path.relpath(prior_shim, harness.shim.parent))
    expected_runsc_link = os.readlink(harness.runsc)
    expected_shim_link = os.readlink(harness.shim)

    installed = harness.run(INSTALL, "--confirm-maintenance")
    assert installed.returncode == 0, installed.stderr
    state = next((harness.state_root / "20260706.0").iterdir())
    assert (state / "original" / "runsc").is_symlink()
    assert (state / "original" / "containerd-shim-runsc-v1").is_symlink()

    restored = harness.run(
        ROLLBACK,
        "--confirm-maintenance",
        "--state-dir",
        str(state),
    )
    assert restored.returncode == 0, restored.stderr
    assert harness.runsc.is_symlink()
    assert harness.shim.is_symlink()
    assert os.readlink(harness.runsc) == expected_runsc_link
    assert os.readlink(harness.shim) == expected_shim_link
    assert prior_runsc.read_bytes() == b"prior-runsc-target"
    assert prior_shim.read_bytes() == b"prior-shim-target"


def test_smoke_image_is_digest_pinned_and_runtime_is_inspected(harness: Harness) -> None:
    result = harness.run(INSTALL, "--confirm-maintenance")

    assert result.returncode == 0, result.stderr
    calls = command_lines(harness)
    create = next(line for line in calls if line.startswith("docker create "))
    assert SMOKE_IMAGE in create
    assert "--runtime=runsc" in create
    assert "--network=none" in create
    assert any("HostConfig.Runtime" in line for line in calls if line.startswith("docker inspect "))


def test_installed_binary_reports_the_exact_pinned_release(harness: Harness) -> None:
    result = harness.run(INSTALL, "--confirm-maintenance")

    assert result.returncode == 0, result.stderr
    version = subprocess.run(
        [str(harness.runsc), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert version.returncode == 0
    assert version.stdout.splitlines()[0] == "runsc version release-20260706.0"


def test_wrong_downloaded_version_triggers_automatic_rollback(harness: Harness) -> None:
    result = harness.run(
        INSTALL,
        "--confirm-maintenance",
        extra_env={"MOCK_RUNSC_VERSION": "release-20260705.0"},
    )

    assert result.returncode != 0
    assert "version" in result.stderr.lower()
    assert not harness.daemon.exists()
    assert not harness.runsc.exists()
    assert not harness.shim.exists()


def test_existing_workloads_and_health_endpoints_are_checked_before_and_after(
    harness: Harness,
) -> None:
    result = harness.run(INSTALL, "--confirm-maintenance")

    assert result.returncode == 0, result.stderr
    calls = command_lines(harness)
    assert sum(line.startswith("docker ps ") for line in calls) >= 2
    existing_inspects = [
        line for line in calls if line.startswith("docker inspect ") and "abc123" in line
    ]
    assert len(existing_inspects) >= 2
    assert any(
        line.startswith("sudo test -f ") and "container-ids.before.txt" in line
        for line in calls
    )
    assert any(
        line.startswith("sudo test -f ") and "container-state.before.txt" in line
        for line in calls
    )
    health_calls = [
        line
        for line in calls
        if line.startswith("curl ")
        and (
            "api.kiaparsaprintingmoneymachine.cloud/" in line
            or "dashboard.kiaparsaprintingmoneymachine.cloud/" in line
        )
    ]
    assert len(health_calls) >= 4
    assert all("--max-time" in line for line in health_calls)


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"MOCK_POST_RUNNING": "false"}, "stopped"),
        ({"MOCK_POST_HEALTH": "unhealthy"}, "unhealthy"),
        ({"MOCK_POST_STARTED_AT": "2026-07-10T00:00:01Z"}, "restarted"),
    ],
)
def test_workload_regression_triggers_automatic_rollback(
    harness: Harness, environment: dict[str, str], message: str
) -> None:
    result = harness.run(INSTALL, "--confirm-maintenance", extra_env=environment)

    assert result.returncode != 0
    assert message in (result.stdout + result.stderr).lower()
    assert "automatic rollback completed" in (result.stdout + result.stderr).lower()
    assert not harness.daemon.exists()
    assert not harness.runsc.exists()
    assert not harness.shim.exists()


def test_smoke_failure_triggers_automatic_rollback(harness: Harness) -> None:
    result = harness.run(
        INSTALL,
        "--confirm-maintenance",
        extra_env={"MOCK_SMOKE_FAIL": "1"},
    )

    assert result.returncode != 0
    assert not harness.daemon.exists()
    assert not harness.runsc.exists()
    assert not harness.shim.exists()
    assert sum("systemctl reload" in line for line in command_lines(harness)) >= 2


def test_bad_health_body_after_reload_triggers_automatic_rollback(harness: Harness) -> None:
    result = harness.run(
        INSTALL,
        "--confirm-maintenance",
        extra_env={"MOCK_HEALTH_BODY_FAIL_AFTER_MUTATION": "1"},
    )

    assert result.returncode != 0
    assert "health" in (result.stdout + result.stderr).lower()
    assert not harness.daemon.exists()
    assert not harness.runsc.exists()
    assert not harness.shim.exists()
    assert sum("systemctl reload" in line for line in command_lines(harness)) >= 2


def test_mock_command_policy_denies_destructive_service_branches(harness: Harness) -> None:
    installed = harness.run(INSTALL, "--confirm-maintenance")

    assert installed.returncode == 0, installed.stderr
    state = next((harness.state_root / "20260706.0").iterdir())
    rolled_back = harness.run(
        ROLLBACK,
        "--confirm-maintenance",
        "--state-dir",
        str(state),
    )
    assert rolled_back.returncode == 0, rolled_back.stderr
    assert not any("DENIED_DESTRUCTIVE" in line for line in command_lines(harness))


def test_test_harness_never_uses_real_host_paths(harness: Harness) -> None:
    assert str(harness.root) != "/"
    assert harness.root.parts[-1] == "host"
    assert not harness.root.is_relative_to(Path("/etc"))
    assert not harness.root.is_relative_to(Path("/usr"))
