"""Unit tests for programmatic MT5 login and reconnect behavior."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

from tania_signal_copier.executor import MT5Executor
from tania_signal_copier.mt5_adapter import LinuxMT5Adapter


class FakeRemoteConnection:
    """Small fake for the RPyC classic connection used by LinuxMT5Adapter."""

    def __init__(self, login_ok: bool = True, account_ok: bool = True) -> None:
        self.login_ok = login_ok
        self.account_ok = account_ok
        self._config: dict[str, object] = {}
        self.execute_calls: list[str] = []
        self.eval_calls: list[str] = []

    def execute(self, code: str) -> None:
        self.execute_calls.append(code)

    def eval(self, code: str) -> Any:
        self.eval_calls.append(code)
        if code.startswith("mt5.initialize("):
            return self.login_ok
        if code == "mt5.shutdown()":
            return None
        if code == "mt5.account_info()":
            return SimpleNamespace(balance=100.0) if self.account_ok else None
        return None


class FakeAdapter:
    """Small fake for MT5Adapter used by MT5Executor tests."""

    TRADE_RETCODE_DONE = 10009

    def __init__(self, initialize_ok: bool = True, login_ok: bool = True, ping_ok: bool = True):
        self.initialize_ok = initialize_ok
        self.login_ok = login_ok
        self.ping_ok = ping_ok
        self.initialize_calls = 0
        self.login_calls: list[tuple[int, str, str]] = []
        self.shutdown_calls = 0

    def initialize(self) -> bool:
        self.initialize_calls += 1
        return self.initialize_ok

    def login(self, login: int, password: str, server: str) -> bool:
        self.login_calls.append((login, password, server))
        return self.login_ok

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def last_error(self) -> tuple[int, str]:
        return (1, "fake error")

    def ping(self) -> bool:
        return self.ping_ok

    def account_info(self) -> SimpleNamespace:
        return SimpleNamespace(
            name="Fake",
            balance=1000.0,
            trade_allowed=True,
        )


def test_linux_adapter_initialize_only_connects_bridge(monkeypatch) -> None:
    fake_conn = FakeRemoteConnection()
    fake_rpyc = SimpleNamespace(
        classic=SimpleNamespace(connect=lambda host, port: fake_conn),
    )
    monkeypatch.setitem(sys.modules, "rpyc", fake_rpyc)

    adapter = LinuxMT5Adapter(host="mt5", port=8001)

    result = adapter.initialize()

    assert result is True
    assert fake_conn.execute_calls == ["import MetaTrader5 as mt5", "import datetime"]
    assert fake_conn.eval_calls == []


def test_linux_adapter_login_initializes_remote_mt5_with_credentials_before_account_check() -> None:
    adapter = LinuxMT5Adapter(host="mt5", port=8001)
    fake_conn = FakeRemoteConnection()
    adapter._conn = fake_conn

    result = adapter.login(login=123456, password="secret", server="Broker-Server")

    assert result is True
    assert fake_conn.eval_calls == [
        "mt5.shutdown()",
        "mt5.initialize(login=123456, password='secret', server='Broker-Server')",
        "mt5.account_info()",
    ]


def test_linux_adapter_login_failure_does_not_accept_existing_account_state() -> None:
    adapter = LinuxMT5Adapter(host="mt5", port=8001)
    fake_conn = FakeRemoteConnection(login_ok=False, account_ok=True)
    adapter._conn = fake_conn

    result = adapter.login(login=123456, password="bad", server="Broker-Server")

    assert result is False
    assert fake_conn.eval_calls == (
        [
            "mt5.shutdown()",
            "mt5.initialize(login=123456, password='bad', server='Broker-Server')",
        ]
    )


def test_linux_adapter_account_check_failure_rejects_initialized_terminal() -> None:
    adapter = LinuxMT5Adapter(host="mt5", port=8001)
    fake_conn = FakeRemoteConnection(login_ok=True, account_ok=False)
    adapter._conn = fake_conn

    result = adapter.login(login=123456, password="secret", server="Broker-Server")

    assert result is False
    assert fake_conn.eval_calls == [
        "mt5.shutdown()",
        "mt5.initialize(login=123456, password='secret', server='Broker-Server')",
        "mt5.account_info()",
    ]


def test_executor_reconfigure_keeps_existing_connection_when_new_login_fails(monkeypatch) -> None:
    old_adapter = FakeAdapter()
    failing_adapter = FakeAdapter(login_ok=False)
    created: list[dict[str, object]] = []

    def fake_create_mt5_adapter(**kwargs: object) -> FakeAdapter:
        created.append(kwargs)
        return failing_adapter

    monkeypatch.setattr(
        "tania_signal_copier.executor.create_mt5_adapter",
        fake_create_mt5_adapter,
    )

    executor = MT5Executor(login=1, password="old", server="old-server")
    executor._mt5 = old_adapter
    executor.connected = True

    result = executor.reconfigure(
        login=2,
        password="new",
        server="new-server",
        docker_host="mt5",
        docker_port=8001,
    )

    assert result["success"] is False
    assert result["connected"] is True
    assert executor._mt5 is old_adapter
    assert old_adapter.shutdown_calls == 0
    assert failing_adapter.shutdown_calls == 1
    assert failing_adapter.login_calls == [(2, "new", "new-server")]
    assert created == [{"host": "mt5", "port": 8001, "path": None}]


def test_concurrent_reconnects_are_single_flight(monkeypatch) -> None:
    old_adapter = FakeAdapter(ping_ok=False)
    new_adapter = FakeAdapter(ping_ok=True)
    create_count = 0

    def fake_create_mt5_adapter(**_kwargs: object) -> FakeAdapter:
        nonlocal create_count
        create_count += 1
        return new_adapter

    monkeypatch.setattr(
        "tania_signal_copier.executor.create_mt5_adapter",
        fake_create_mt5_adapter,
    )
    monkeypatch.setattr("tania_signal_copier.executor.time.sleep", lambda _seconds: None)

    executor = MT5Executor(login=1, password="secret", server="Broker-Server")
    executor._mt5 = old_adapter
    executor.connected = True

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _index: executor._reconnect(), range(50)))

    assert all(results)
    assert create_count == 1
    assert old_adapter.shutdown_calls == 1
    assert new_adapter.initialize_calls == 1
    assert new_adapter.login_calls == [(1, "secret", "Broker-Server")]
    assert executor._mt5 is new_adapter
