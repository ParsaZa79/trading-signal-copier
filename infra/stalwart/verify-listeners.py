#!/usr/bin/env python3
"""Validate a Stalwart v0.16 NetworkListener NDJSON snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


POLICY_PATH = Path(__file__).with_name("listener-policy.json")


def load_policy() -> dict[str, Any]:
    value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("listener policy must be an object")
    return value


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"line {line_number}: listener must be a JSON object")
        records.append(value)
    return records


def binding_ports(listener: dict[str, Any], errors: list[str]) -> set[int]:
    name = str(listener.get("name", "<unnamed>"))
    bindings = listener.get("bind")
    if not isinstance(bindings, list) or not bindings:
        errors.append(f"listener {name!r} has no valid bind list")
        return set()

    ports: set[int] = set()
    for binding in bindings:
        if not isinstance(binding, str) or ":" not in binding:
            errors.append(f"listener {name!r} has invalid bind address {binding!r}")
            continue
        raw_port = binding.rsplit(":", 1)[1]
        try:
            port = int(raw_port)
        except ValueError:
            errors.append(f"listener {name!r} has invalid port in {binding!r}")
            continue
        if not 1 <= port <= 65535:
            errors.append(f"listener {name!r} has out-of-range port {port}")
            continue
        ports.add(port)
    return ports


def verify(records: list[dict[str, Any]], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {item["name"]: item for item in policy["required"]}
    forbidden_ports = {int(port) for port in policy["forbiddenPorts"]}
    forbidden_protocols = {str(value).casefold() for value in policy["forbiddenProtocols"]}
    seen: dict[str, int] = {}

    for listener in records:
        name = str(listener.get("name", "<unnamed>"))
        protocol = str(listener.get("protocol", "<missing>"))
        ports = binding_ports(listener, errors)
        seen[name] = seen.get(name, 0) + 1

        blocked = sorted(ports & forbidden_ports)
        if blocked:
            errors.append(f"listener {name!r} uses forbidden port(s): {blocked}")
        if protocol.casefold() in forbidden_protocols:
            errors.append(f"listener {name!r} uses forbidden protocol {protocol!r}")

        expected = required.get(name)
        if expected is None:
            errors.append(
                f"unexpected listener {name!r}: protocol={protocol!r}, ports={sorted(ports)}"
            )
            continue

        expected_ports = {int(port) for port in expected["ports"]}
        expected_bindings = expected["bind"]
        if protocol != expected["protocol"]:
            errors.append(
                f"listener {name!r} protocol is {protocol!r}, expected {expected['protocol']!r}"
            )
        if ports != expected_ports:
            errors.append(
                f"listener {name!r} ports are {sorted(ports)}, expected {sorted(expected_ports)}"
            )
        if listener.get("bind") != expected_bindings:
            errors.append(
                f"listener {name!r} bind is {listener.get('bind')!r}, "
                f"expected {expected_bindings!r}"
            )
        if listener.get("useTls") is not expected["useTls"]:
            errors.append(
                f"listener {name!r} useTls is {listener.get('useTls')!r}, "
                f"expected {expected['useTls']!r}"
            )
        if listener.get("tlsImplicit") is not expected["tlsImplicit"]:
            errors.append(
                f"listener {name!r} tlsImplicit is {listener.get('tlsImplicit')!r}, "
                f"expected {expected['tlsImplicit']!r}"
            )

    for name in required:
        count = seen.get(name, 0)
        if count == 0:
            errors.append(f"required listener {name!r} is missing")
        elif count > 1:
            errors.append(f"required listener {name!r} appears {count} times")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Stalwart NetworkListener NDJSON against listener-policy.json."
    )
    parser.add_argument("snapshot", type=Path, help="NDJSON produced by stalwart-cli query")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        errors = verify(load_snapshot(args.snapshot), load_policy())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"listener verification failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("listener policy violation(s):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Listener policy verified: only SMTP 25 and submission 587 are enabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
