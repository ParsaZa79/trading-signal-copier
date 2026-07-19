from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
STALWART = ROOT / "infra" / "stalwart"


def load_yaml(name: str) -> dict[str, Any]:
    value = yaml.safe_load((STALWART / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def environment_map(service: dict[str, Any]) -> dict[str, Any]:
    environment = service.get("environment", {})
    if isinstance(environment, dict):
        return environment
    result: dict[str, Any] = {}
    for item in environment:
        key, separator, value = str(item).partition("=")
        result[key] = value if separator else None
    return result


def test_base_compose_has_only_public_smtp_and_private_submission() -> None:
    compose = load_yaml("compose.yaml")
    stalwart = compose["services"]["stalwart"]

    assert stalwart["image"] == "stalwartlabs/stalwart:v0.16@sha256:b30c99ed8240ea42612f784babe0388318d5c3668a77873efe7e3b1147e2226e"
    assert stalwart["hostname"] == "mail.kiaparsaprintingmoneymachine.cloud"
    assert environment_map(stalwart) == {}

    ports = stalwart["ports"]
    assert ports == [
        {
            "name": "smtp",
            "target": 25,
            "published": "25",
            "protocol": "tcp",
        }
    ]
    assert {int(port) for port in stalwart["expose"]} == {587}
    assert stalwart["labels"] == {"traefik.enable": "false"}

    assert set(stalwart["networks"]) == {"mail-private"}
    assert stalwart["networks"]["mail-private"]["aliases"] == [
        "stalwart",
        "mail.kiaparsaprintingmoneymachine.cloud",
    ]
    assert compose["networks"] == {
        "mail-private": {"external": True, "name": "trading-platform-mail"}
    }


def test_base_compose_cannot_enable_recovery_or_admin_http() -> None:
    compose = load_yaml("compose.yaml")
    stalwart = compose["services"]["stalwart"]
    environment = environment_map(stalwart)

    assert "STALWART_RECOVERY_ADMIN" not in environment
    assert "STALWART_RECOVERY_MODE" not in environment
    assert all(port["target"] not in {80, 443, 8080} for port in stalwart["ports"])
    assert 8080 not in {int(port) for port in stalwart["expose"]}


def test_dedicated_network_policy_allows_only_stalwart_and_dashboard() -> None:
    policy = load_yaml("network-policy.yaml")

    assert policy["runtime_ownership"] == {
        "stalwart": {
            "manager": "standalone-docker-compose",
            "compose_project": "trading-platform-mail",
        },
        "dashboard": {
            "manager": "dokploy-application",
            "application_id": "lku4v_DVjO_BEJSSQgBZi",
        },
    }
    assert policy["network"] == {
        "name": "trading-platform-mail",
        "driver": "overlay",
        "attachable": True,
        "internal": False,
    }
    assert policy["allowed_members"] == [
        {"role": "stalwart", "compose_service": "stalwart", "alias": "stalwart"},
        {
            "role": "dashboard",
            "dokploy_application_id": "lku4v_DVjO_BEJSSQgBZi",
            "alias": "trading-dashboard",
        },
    ]
    assert set(policy["explicitly_forbidden_roles"]) == {"api", "mt5", "traefik"}


def test_bootstrap_compose_is_standalone_isolated_and_requires_a_secret() -> None:
    bootstrap = load_yaml("compose.bootstrap.yaml")
    stalwart = bootstrap["services"]["stalwart"]

    assert bootstrap["name"] == "trading-platform-mail"
    assert stalwart["image"] == "stalwartlabs/stalwart:v0.16@sha256:b30c99ed8240ea42612f784babe0388318d5c3668a77873efe7e3b1147e2226e"
    assert environment_map(stalwart) == {
        "STALWART_RECOVERY_ADMIN": (
            "${STALWART_RECOVERY_ADMIN:?bootstrap-only recovery credential required}"
        )
    }
    assert stalwart["ports"] == [
        {
            "name": "bootstrap-admin",
            "target": 8080,
            "published": "18080",
            "host_ip": "127.0.0.1",
            "protocol": "tcp",
        }
    ]
    assert "expose" not in stalwart
    assert set(stalwart["networks"]) == {"bootstrap-admin"}
    assert stalwart["labels"] == {"traefik.enable": "false"}
    assert bootstrap["networks"] == {
        "bootstrap-admin": {"driver": "bridge", "internal": False}
    }
    assert bootstrap["volumes"] == {
        "stalwart-config": {"name": "trading-platform-mail-stalwart-config"},
        "stalwart-data": {"name": "trading-platform-mail-stalwart-data"},
    }

    recovery = load_yaml("compose.recovery.yaml")
    assert environment_map(recovery["services"]["stalwart"]) == {
        "STALWART_RECOVERY_MODE": "1"
    }


def test_listener_policy_disables_every_unused_protocol() -> None:
    policy = json.loads((STALWART / "listener-policy.json").read_text(encoding="utf-8"))

    assert policy["required"] == [
        {
            "name": "smtp",
            "protocol": "smtp",
            "bind": ["[::]:25"],
            "ports": [25],
            "useTls": True,
            "tlsImplicit": False,
        },
        {
            "name": "submission",
            "protocol": "smtp",
            "bind": ["[::]:587"],
            "ports": [587],
            "useTls": True,
            "tlsImplicit": False,
        },
    ]
    assert set(policy["forbiddenPorts"]) == {
        24,
        80,
        110,
        143,
        443,
        465,
        993,
        995,
        4190,
        8080,
    }
    assert set(policy["forbiddenProtocols"]) == {"http", "imap", "pop3", "manageSieve", "lmtp"}


def test_listener_verifier_accepts_only_the_policy(tmp_path: Path) -> None:
    snapshot = tmp_path / "listeners.ndjson"
    snapshot.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "a",
                        "name": "smtp",
                        "protocol": "smtp",
                        "bind": ["[::]:25"],
                        "useTls": True,
                        "tlsImplicit": False,
                    }
                ),
                json.dumps(
                    {
                        "id": "b",
                        "name": "submission",
                        "protocol": "smtp",
                        "bind": ["[::]:587"],
                        "useTls": True,
                        "tlsImplicit": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python3", str(STALWART / "verify-listeners.py"), str(snapshot)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "listener policy verified" in result.stdout.lower()


def test_listener_verifier_rejects_admin_and_imap(tmp_path: Path) -> None:
    snapshot = tmp_path / "listeners.ndjson"
    snapshot.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "a",
                        "name": "smtp",
                        "protocol": "smtp",
                        "bind": ["[::]:25"],
                        "useTls": True,
                        "tlsImplicit": False,
                    }
                ),
                json.dumps(
                    {
                        "id": "b",
                        "name": "submission",
                        "protocol": "smtp",
                        "bind": ["[::]:587"],
                        "useTls": True,
                        "tlsImplicit": False,
                    }
                ),
                json.dumps(
                    {
                        "id": "c",
                        "name": "admin",
                        "protocol": "http",
                        "bind": ["[::]:8080"],
                        "useTls": False,
                        "tlsImplicit": False,
                    }
                ),
                json.dumps(
                    {
                        "id": "d",
                        "name": "imap",
                        "protocol": "imap",
                        "bind": ["[::]:143"],
                        "useTls": True,
                        "tlsImplicit": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python3", str(STALWART / "verify-listeners.py"), str(snapshot)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "8080" in result.stderr
    assert "imap" in result.stderr.lower()


@pytest.mark.parametrize(
    ("listener_name", "bindings"),
    [
        ("smtp", ["127.0.0.1:25"]),
        ("smtp", ["[::]:25", "0.0.0.0:25"]),
        ("submission", ["0.0.0.0:587"]),
        ("submission", ["[::]:587", "[::1]:587"]),
        ("submission", ["[::]:587", "[::]:587"]),
    ],
)
def test_listener_verifier_rejects_non_exact_bindings(
    tmp_path: Path,
    listener_name: str,
    bindings: list[str],
) -> None:
    listeners = [
        {
            "id": "a",
            "name": "smtp",
            "protocol": "smtp",
            "bind": ["[::]:25"],
            "useTls": True,
            "tlsImplicit": False,
        },
        {
            "id": "b",
            "name": "submission",
            "protocol": "smtp",
            "bind": ["[::]:587"],
            "useTls": True,
            "tlsImplicit": False,
        },
    ]
    next(item for item in listeners if item["name"] == listener_name)["bind"] = bindings
    snapshot = tmp_path / "listeners.ndjson"
    snapshot.write_text(
        "\n".join(json.dumps(item) for item in listeners) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python3", str(STALWART / "verify-listeners.py"), str(snapshot)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "bind" in result.stderr.lower()


def _write_mock_docker(path: Path) -> Path:
    executable = path / "docker"
    executable.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "${MOCK_DOCKER_LOG:?}"
if [[ "${1:-}" == "compose" && " $* " == *" ps -q stalwart "* ]]; then
  printf '%s\\n' stalwart-container
  exit 0
fi
if [[ "${1:-}" == "compose" && " $* " == *" up "* && "${MOCK_COMPOSE_UP_FAIL:-0}" == "1" ]]; then
  exit 44
fi
if [[ "${1:-}" == "compose" && " $* " == *" down "* && "${MOCK_COMPOSE_DOWN_FAIL:-0}" == "1" ]]; then
  exit 45
fi
if [[ "${1:-}" == "version" ]]; then
  printf '%s\\n' "${MOCK_DOCKER_VERSION:-28.0.0}"
  exit 0
fi
if [[ "${1:-}" == "inspect" ]]; then
  if [[ "$*" == *"HostConfig.PortBindings"* ]]; then
    if [[ "${MOCK_ADMIN_BINDING:-absent}" == "safe" ]]; then
      printf '%s\\n' '{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"18080"}]}'
    elif [[ "${MOCK_ADMIN_BINDING:-absent}" == "public" ]]; then
      printf '%s\\n' '{"8080/tcp":[{"HostIp":"0.0.0.0","HostPort":"18080"}]}'
    else
      printf '%s\\n' '{}'
    fi
  elif [[ "$*" == *"NetworkSettings.Networks"* ]]; then
    if [[ "${MOCK_MAIL_NETWORK:-0}" == "1" ]]; then
      printf '%s\\n' '{"trading-platform-mail":{}}'
    else
      printf '%s\\n' '{"trading-platform-mail_bootstrap-admin":{}}'
    fi
  elif [[ "${MOCK_RECOVERY_PRESENT:-0}" == "1" ]]; then
    printf '%s\\n' '["STALWART_RECOVERY_ADMIN=redacted"]'
  elif [[ "${MOCK_RECOVERY_MODE:-0}" == "1" ]]; then
    printf '%s\\n' '["STALWART_RECOVERY_ADMIN=redacted","STALWART_RECOVERY_MODE=1"]'
  else
      printf '%s\\n' '["PATH=/usr/local/bin:/usr/bin:/bin"]'
  fi
  exit 0
fi
exit 0
""",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def test_bootstrap_removal_recreates_from_base_and_proves_env_absent(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_RECOVERY_PRESENT": "0",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "remove", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    recreate = next(call for call in calls if " up " in f" {call} ")
    assert "compose.bootstrap.yaml" not in recreate
    assert "compose.yaml" in recreate
    assert "--force-recreate" in recreate
    assert any(call.startswith("inspect ") for call in calls)


def test_bootstrap_removal_fails_if_recovery_env_survives(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_RECOVERY_PRESENT": "1",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "remove", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "still present" in result.stderr.lower()
    assert "redacted" not in result.stdout + result.stderr
    assert any(
        " down " in f" {line} " and "--remove-orphans" in line
        for line in log.read_text(encoding="utf-8").splitlines()
    )


def test_bootstrap_removal_fails_if_admin_port_survives(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_ADMIN_BINDING": "safe",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "remove", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "port 8080 is still bound" in result.stderr
    assert any(
        " down " in f" {line} " and "--remove-orphans" in line
        for line in log.read_text(encoding="utf-8").splitlines()
    )


def test_partial_bootstrap_up_failure_is_torn_down(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_COMPOSE_UP_FAIL": "1",
            "STALWART_RECOVERY_ADMIN": "bootstrap-user:not-a-real-secret",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "start", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    calls = log.read_text(encoding="utf-8").splitlines()
    up_index = next(index for index, line in enumerate(calls) if " up " in f" {line} ")
    down_index = next(
        index
        for index, line in enumerate(calls)
        if " down " in f" {line} " and "--remove-orphans" in line
    )
    assert up_index < down_index


def test_bootstrap_cleanup_failure_never_claims_secret_container_was_removed(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_COMPOSE_UP_FAIL": "1",
            "MOCK_COMPOSE_DOWN_FAIL": "1",
            "STALWART_RECOVERY_ADMIN": "bootstrap-user:not-a-real-secret",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "start", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "critical" in result.stderr.lower()
    assert "may remain" in result.stderr.lower()
    assert "was removed" not in result.stderr.lower()
    assert "not-a-real-secret" not in result.stdout + result.stderr


def test_recovery_stage_uses_isolated_compose_and_explicit_recovery_mode(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_DOCKER_VERSION": "28.1.0",
            "MOCK_ADMIN_BINDING": "safe",
            "MOCK_RECOVERY_MODE": "1",
            "STALWART_RECOVERY_ADMIN": "bootstrap-user:not-a-real-secret",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "recovery", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    up_call = next(
        line
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.startswith("compose ") and " up " in f" {line} "
    )
    assert "compose.bootstrap.yaml" in up_call
    assert "compose.recovery.yaml" in up_call
    assert "compose.yaml" not in up_call.replace("compose.bootstrap.yaml", "").replace(
        "compose.recovery.yaml", ""
    )
    assert "--project-name trading-platform-mail" in up_call
    assert any("NetworkSettings.Networks" in line for line in log.read_text().splitlines())


def test_mounted_tls_fallback_is_wired_through_recovery_and_base_removal(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_ADMIN_BINDING": "safe",
            "MOCK_RECOVERY_MODE": "1",
            "STALWART_RECOVERY_ADMIN": "bootstrap-user:not-a-real-secret",
        }
    )

    recovery = subprocess.run(
        [
            str(STALWART / "bootstrap.sh"),
            "recovery",
            "--confirm-maintenance",
            "--tls-mounted",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert recovery.returncode == 0, recovery.stderr
    assert "remove --confirm-maintenance --tls-mounted" in recovery.stdout
    recovery_up = next(
        line
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.startswith("compose ") and " up " in f" {line} "
    )
    assert "compose.bootstrap.yaml" in recovery_up
    assert "compose.recovery.yaml" in recovery_up
    assert "compose.tls-mounted.yaml" in recovery_up

    log.write_text("", encoding="utf-8")
    env["MOCK_RECOVERY_MODE"] = "0"
    env["MOCK_ADMIN_BINDING"] = "absent"
    removal = subprocess.run(
        [
            str(STALWART / "bootstrap.sh"),
            "remove",
            "--confirm-maintenance",
            "--tls-mounted",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert removal.returncode == 0, removal.stderr
    removal_up = next(
        line
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.startswith("compose ") and " up " in f" {line} "
    )
    assert "compose.yaml" in removal_up
    assert "compose.tls-mounted.yaml" in removal_up
    assert "compose.bootstrap.yaml" not in removal_up
    assert "compose.recovery.yaml" not in removal_up


def test_mounted_tls_flag_is_rejected_for_first_boot(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "STALWART_RECOVERY_ADMIN": "bootstrap-user:not-a-real-secret",
        }
    )

    result = subprocess.run(
        [
            str(STALWART / "bootstrap.sh"),
            "start",
            "--confirm-maintenance",
            "--tls-mounted",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "recovery and remove" in result.stderr.lower()
    assert not log.exists() or not log.read_text(encoding="utf-8")


def test_bootstrap_rejects_attachment_to_the_dashboard_mail_network(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_DOCKER_VERSION": "28.1.0",
            "MOCK_ADMIN_BINDING": "safe",
            "MOCK_MAIL_NETWORK": "1",
            "MOCK_RECOVERY_PRESENT": "1",
            "STALWART_RECOVERY_ADMIN": "bootstrap-user:not-a-real-secret",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "start", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "isolated bootstrap network" in result.stderr


def test_bootstrap_pins_the_compose_project_against_environment_override(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "COMPOSE_PROJECT_NAME": "hostile-parallel-project",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "remove", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    compose_calls = [
        line
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.startswith("compose ") and (" up " in f" {line} " or " ps " in f" {line} ")
    ]
    assert compose_calls
    assert all("--project-name trading-platform-mail" in line for line in compose_calls)
    assert all("hostile-parallel-project" not in line for line in compose_calls)


def test_bootstrap_refuses_loopback_admin_on_docker_before_28(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_mock_docker(fake_bin)
    log = tmp_path / "docker.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "MOCK_DOCKER_LOG": str(log),
            "MOCK_DOCKER_VERSION": "27.5.1",
            "STALWART_RECOVERY_ADMIN": "bootstrap-user:not-a-real-secret",
        }
    )

    result = subprocess.run(
        [str(STALWART / "bootstrap.sh"), "start", "--confirm-maintenance"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Docker Engine 28.0.0 or newer" in result.stderr
    assert not any(" up " in f" {line} " for line in log.read_text(encoding="utf-8").splitlines())


def test_local_mailpit_is_loopback_only_and_does_not_publish_smtp() -> None:
    compose = load_yaml("compose.local.yaml")
    mailpit = compose["services"]["mailpit"]

    assert mailpit["image"] == (
        "axllent/mailpit:v1.30.0@sha256:"
        "0059ef81e492a7192af3816281eed6859eb078bd7bdc58b76757c13e10e53a7d"
    )
    assert mailpit["ports"] == [
        {
            "name": "mailpit-ui",
            "target": 8025,
            "published": "8025",
            "host_ip": "127.0.0.1",
            "protocol": "tcp",
        }
    ]
    assert {int(port) for port in mailpit["expose"]} == {1025}
    assert compose["networks"]["mailpit-local"]["internal"] is True


def test_tls_and_backup_policies_are_machine_readable_and_concrete() -> None:
    tls = load_yaml("tls-policy.yaml")
    assert tls["primary"]["challenge"] == "dns-01"
    assert tls["primary"]["dns_provider"] == "hostinger"
    assert tls["primary"]["requires_host_ports"] == []
    assert tls["primary"]["default_certificate_required"] is True
    assert tls["external_acme_fallback"] == {
        "fullchain": "/run/stalwart-tls/fullchain.pem",
        "private_key": "/run/stalwart-tls/privkey.pem",
        "mount_read_only": True,
        "default_certificate_required": True,
        "default_certificate_field": "SystemSettings.defaultCertificateId",
        "runtime_default_probe": "smtp-starttls-no-sni",
        "reload_action": "Action/ReloadTlsCertificates",
    }

    mounted_tls = load_yaml("compose.tls-mounted.yaml")
    assert mounted_tls["services"]["stalwart"]["volumes"] == [
        {
            "type": "volume",
            "source": "stalwart-tls",
            "target": "/run/stalwart-tls",
            "read_only": True,
        }
    ]
    assert mounted_tls["volumes"]["stalwart-tls"] == {
        "external": True,
        "name": "trading-platform-mail-stalwart-tls",
    }
    manual_certificate = json.loads(
        (STALWART / "certificate.manual.json").read_text(encoding="utf-8")
    )
    assert manual_certificate == {
        "certificate": {
            "@type": "File",
            "filePath": "/run/stalwart-tls/fullchain.pem",
        },
        "privateKey": {
            "@type": "File",
            "filePath": "/run/stalwart-tls/privkey.pem",
        },
    }

    backup = load_yaml("backup-policy.yaml")
    assert backup["schedule"] == "15 2 * * *"
    assert backup["timezone"] == "UTC"
    assert backup["consistency"] == "stopped-container-or-storage-snapshot"
    assert backup["retention"] == {"daily": 7, "weekly": 5, "monthly": 12}
    assert backup["off_host"]["client_side_encryption"] is True
    assert backup["off_host"]["object_lock"] is True
    assert backup["restore_test"]["frequency"] == "quarterly"
    assert backup["restore_test"]["rpo_hours"] == 24
    assert backup["restore_test"]["rto_hours"] == 4


def test_operational_check_script_is_read_only_by_contract() -> None:
    result = subprocess.run(
        [str(STALWART / "check-mail.sh"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "dns" in result.stdout.lower()
    assert "starttls" in result.stdout.lower()
    assert "relay" in result.stdout.lower()
    forbidden = {"docker", "dokploy", "systemctl", "sudo"}
    words = set((result.stdout + result.stderr).lower().split())
    assert forbidden.isdisjoint(words)


def test_smtp_check_emits_and_can_require_leaf_certificate_fingerprint(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    openssl = fake_bin / "openssl"
    openssl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "s_client" ]]; then
  printf '%s\\n' "$*" >> "${MOCK_OPENSSL_LOG:?}"
  printf '%s\\n' '-----BEGIN CERTIFICATE-----' 'mock' '-----END CERTIFICATE-----'
elif [[ "${1:-}" == "x509" && "$*" == *"-fingerprint"* ]]; then
  printf '%s\\n' 'sha256 Fingerprint=AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99'
  [[ "$*" != *"-serial"* ]] || printf '%s\\n' 'serial=0123456789ABCDEF'
  [[ "$*" != *"-enddate"* ]] || printf '%s\\n' 'notAfter=Aug 10 00:00:00 2026 GMT'
else
  exit 2
fi
""",
        encoding="utf-8",
    )
    openssl.chmod(openssl.stat().st_mode | stat.S_IXUSR)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["MOCK_OPENSSL_LOG"] = str(tmp_path / "openssl.log")
    expected = "AABBCCDDEEFF00112233445566778899AABBCCDDEEFF00112233445566778899"

    passed = subprocess.run(
        [
            str(STALWART / "check-mail.sh"),
            "--smtp-only",
            "--expected-sha256-fingerprint",
            expected,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert passed.returncode == 0, passed.stderr
    assert "serial=0123456789ABCDEF" in passed.stdout
    assert "notAfter=Aug 10 00:00:00 2026 GMT" in passed.stdout
    assert "sha256 Fingerprint=" in passed.stdout

    no_sni = subprocess.run(
        [
            str(STALWART / "check-mail.sh"),
            "--smtp-only",
            "--no-sni",
            "--expected-sha256-fingerprint",
            expected,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert no_sni.returncode == 0, no_sni.stderr
    s_client_calls = (tmp_path / "openssl.log").read_text(encoding="utf-8").splitlines()
    assert any("-servername" in call for call in s_client_calls)
    no_sni_call = next(call for call in s_client_calls if "-noservername" in call)
    assert "-servername" not in no_sni_call
    assert "-verify_hostname mail.kiaparsaprintingmoneymachine.cloud" in no_sni_call

    rejected = subprocess.run(
        [
            str(STALWART / "check-mail.sh"),
            "--smtp-only",
            "--expected-sha256-fingerprint",
            "0" * 64,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode != 0
    assert "fingerprint" in rejected.stderr.lower()


def test_runbook_covers_every_mandatory_gate_without_public_admin_guidance() -> None:
    readme = (STALWART / "README.md").read_text(encoding="utf-8")
    headings = {
        line.removeprefix("## ").strip().casefold()
        for line in readme.splitlines()
        if line.startswith("## ")
    }

    required_heading_terms = {
        "bootstrap",
        "network",
        "listener",
        "tls",
        "mailpit",
        "relay",
        "deliverability",
        "backup",
        "restore",
    }
    assert all(any(term in heading for heading in headings) for term in required_heading_terms)
    assert "Route `https://mail.kiaparsaprintingmoneymachine.cloud`" not in readme
    assert "traefik.enable: false" in readme
    assert "--driver overlay" in readme
    assert "--attachable" in readme
    assert "--internal" in readme
    assert "stalwart-cli query NetworkListener" in readme
    assert "verify-listeners.py" in readme
    assert "Action/ReloadTlsCertificates" in readme
    assert "SystemSettings.defaultCertificateId" in readme
    assert "stalwart-cli update SystemSettings --field" in readme
    assert "stalwart-cli create Action/ReloadTlsCertificates" in readme
    assert "--no-sni" in readme
    assert "recovery --confirm-maintenance --tls-mounted" in readme
    assert "remove --confirm-maintenance --tls-mounted" in readme
    assert "standalone Docker Compose outside Dokploy" in readme
    assert "sha256:b30c99ed8240ea42612f784babe0388318d5c3668a77873efe7e3b1147e2226e" in readme
    assert "short image tag tracks" not in readme
    assert "OPEN_SIGNUP_ENABLED=false" in readme
    assert "7 daily" in readme
    assert "5 weekly" in readme
    assert "12 monthly" in readme
    assert "client-side encryption" in readme.lower()
    assert "quarterly" in readme.lower()
    assert "https://stalw.art/docs/" in readme
    assert "https://docs.dokploy.com/" in readme
