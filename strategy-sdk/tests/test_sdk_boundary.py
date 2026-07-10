from __future__ import annotations

import ast
from pathlib import Path

SDK_SOURCE = Path(__file__).resolve().parents[1] / "src" / "trading_strategy_sdk"
FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp",
    "httpx",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "tempfile",
    "urllib",
}
FORBIDDEN_BUILTINS = {"__import__", "compile", "eval", "exec", "open"}


def test_sdk_has_no_network_filesystem_shell_or_dynamic_runtime_access() -> None:
    violations: list[str] = []

    for source_path in sorted(SDK_SOURCE.glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.partition(".")[0] for alias in node.names}
                forbidden = roots & FORBIDDEN_IMPORT_ROOTS
                if forbidden:
                    violations.append(
                        f"{source_path.name}:{node.lineno}: import {sorted(forbidden)}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                root = node.module.partition(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(f"{source_path.name}:{node.lineno}: import {root}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in FORBIDDEN_BUILTINS
            ):
                violations.append(f"{source_path.name}:{node.lineno}: call {node.func.id}")

    assert not violations, "SDK boundary violations:\n" + "\n".join(violations)
