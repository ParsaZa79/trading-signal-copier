from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MT5 = REPO_ROOT / "mt5"
BASE_DIGEST = "sha256:2fdff449cf70b74c242319828b6859592ab52dfb05690d9a989c75107dabf4c1"
RPYC_WHEEL_SHA256 = "8072308ad30725bc281c42c011fc8c922be15f3eeda6eafb2917cafe1b6f00ec"
MT5LINUX_WHEEL_SHA256 = "6cafa7f4b95470aa62877e1989c03be04f20d786d55f94e92aaefa1bf084e802"
PLUMBUM_WHEEL_SHA256 = "139bbe08ee065b522a8a07d4f7e9f8eddffd78cc218b65b11cca2b33683e6b57"
NUMPY_WHEEL_SHA256 = "89cd468399cfd2504718f0ba50e410dca55a170b61a02ad92bb18c8a65186e93"
WINE_NUMPY_WHEEL_SHA256 = "a354325ee03388678242a4d7ebcd08b5c727033fcff3b2f536aea978e15ee9e6"


def test_mt5_image_pins_base_and_rpyc_wheel_integrity() -> None:
    dockerfile = (MT5 / "Dockerfile").read_text(encoding="utf-8")

    assert f"gmag11/metatrader5_vnc@{BASE_DIGEST}" in dockerfile
    assert "rpyc-6.0.2-py3-none-any.whl" in dockerfile
    assert "mt5linux-0.1.9-py3-none-any.whl" in dockerfile
    assert "plumbum-1.7.0-py2.py3-none-any.whl" in dockerfile
    assert "numpy-2.4.6-cp311-cp311-manylinux" in dockerfile
    assert "numpy-1.26.4-cp39-cp39-win32.whl" in dockerfile
    assert RPYC_WHEEL_SHA256 in dockerfile
    assert MT5LINUX_WHEEL_SHA256 in dockerfile
    assert PLUMBUM_WHEEL_SHA256 in dockerfile
    assert NUMPY_WHEEL_SHA256 in dockerfile
    assert WINE_NUMPY_WHEEL_SHA256 in dockerfile
    assert "sha256sum -c" in dockerfile
    assert "/custom-cont-init.d" not in dockerfile


def test_mt5_startup_patch_pins_linux_client_and_wine_server_rpyc() -> None:
    patch_script = (MT5 / "patch-start.py").read_text(encoding="utf-8")

    assert "mt5linux-0.1.9-py3-none-any.whl" in patch_script
    assert "rpyc-6.0.2-py3-none-any.whl" in patch_script
    assert "plumbum-1.7.0-py2.py3-none-any.whl" in patch_script
    assert "numpy-2.4.6-cp311-cp311-manylinux" in patch_script
    assert "numpy-1.26.4-cp39-cp39-win32.whl" in patch_script
    assert "--no-index" in patch_script
    assert "--no-deps" in patch_script
    assert "--force-reinstall" in patch_script
    assert "$wine_executable python -m pip" in patch_script
    assert "python3 -m pip install --user" in patch_script
    assert patch_script.count("|| exit 1") >= 4
    assert "rpyc.__version__" in patch_script
    assert "mt5linux" in patch_script


def test_production_compose_never_publishes_rpyc_classic() -> None:
    compose = (MT5 / "compose.yaml").read_text(encoding="utf-8")

    assert "8001:8001" not in compose
    assert '"8001"' in compose
    assert "trading-mt5-api" in compose
    assert "dokploy-network" not in compose
    assert "external: true" in compose
    assert "gmag11/metatrader5_vnc:latest" not in compose


def test_local_rpyc_binding_and_start_script_are_loopback_only() -> None:
    local_compose = (MT5 / "compose.local.yaml").read_text(encoding="utf-8")
    start_script = (REPO_ROOT / "start-linux.sh").read_text(encoding="utf-8")

    assert re.search(r"127\.0\.0\.1:\$\{MT5_RPYC_PORT:-8001\}:8001", local_compose)
    assert "mt5/compose.local.yaml" in start_script
    assert "-p 8001:8001" not in start_script


def test_rpyc_security_documentation_forbids_public_classic_service() -> None:
    readme = " ".join((MT5 / "README.md").read_text(encoding="utf-8").lower().split())

    assert "never" in readme
    assert "public" in readme
    assert "authentication" in readme
    assert "tls" in readme
    assert "private container network" in readme
