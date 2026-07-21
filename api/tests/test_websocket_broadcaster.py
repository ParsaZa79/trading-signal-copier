from __future__ import annotations

from types import SimpleNamespace

from src.websocket.broadcaster import RuntimeSnapshotCache


def _account(balance: float = 10_000) -> SimpleNamespace:
    return SimpleNamespace(
        balance=balance,
        equity=balance,
        margin=0.0,
        margin_free=balance,
        profit=0.0,
    )


class _SequenceExecutor:
    def __init__(self, snapshots: list[object]) -> None:
        self.snapshots = snapshots
        self.recoveries = 0

    def get_dashboard_snapshot(self):
        value = self.snapshots.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def recover_connection(self) -> bool:
        self.recoveries += 1
        return True


async def test_transient_mt5_miss_keeps_last_valid_dashboard_snapshot() -> None:
    now = [100.0]
    executor = _SequenceExecutor(
        [
            ([], _account()),
            RuntimeError("temporary account_info miss"),
            RuntimeError("temporary account_info miss"),
        ]
    )
    cache = RuntimeSnapshotCache(
        grace_seconds=12,
        recovery_after_failures=10,
        clock=lambda: now[0],
    )

    connected = await cache.build_update(executor, "account-1")
    now[0] += 1
    degraded = await cache.build_update(executor, "account-1")

    assert connected["connection"]["status"] == "connected"
    assert degraded["connection"]["status"] == "degraded"
    assert degraded["connection"]["stale"] is True
    assert degraded["account"] == connected["account"]

    now[0] += 13
    disconnected = await cache.build_update(executor, "account-1")
    assert disconnected["connection"]["status"] == "disconnected"
    assert disconnected["account"] is None


async def test_repeated_snapshot_failures_recover_the_runtime_once() -> None:
    now = [200.0]
    executor = _SequenceExecutor(
        [
            ([], _account()),
            RuntimeError("read 1"),
            RuntimeError("read 2"),
            RuntimeError("read 3"),
            ([], _account(10_050)),
        ]
    )
    cache = RuntimeSnapshotCache(
        recovery_after_failures=3,
        recovery_cooldown_seconds=15,
        clock=lambda: now[0],
    )

    await cache.build_update(executor, "account-1")
    now[0] += 1
    await cache.build_update(executor, "account-1")
    now[0] += 1
    await cache.build_update(executor, "account-1")
    now[0] += 1
    recovered = await cache.build_update(executor, "account-1")

    assert executor.recoveries == 1
    assert recovered["connection"]["status"] == "connected"
    assert recovered["account"]["balance"] == 10_050
