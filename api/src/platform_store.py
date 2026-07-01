"""Paper-first platform domain for providers, copy trading, and trade events.

The existing bot can still execute Telegram signals directly on MT5. This module adds a
neutral platform layer that future sources can target first:

source -> TradeEvent -> Risk policy -> PaperExecution/live execution adapter.

For the MVP this store is intentionally JSON-backed, matching the rest of the current
local dashboard data model. The public functions are side-effect bounded and avoid any
broker calls; all executions created here are paper/simulated unless a future adapter is
explicitly wired in.
"""

from __future__ import annotations

import json
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .runtime_data import DATA_DIR

PLATFORM_PATH = DATA_DIR / "platform.json"

_ALLOWED_COPY_MODES = {"fixed_lot", "multiplier", "mirror"}
_ALLOWED_EVENT_ACTIONS = {"open", "modify", "close", "partial_close"}
_ALLOWED_SIDES = {"buy", "sell"}
_ALLOWED_VISIBILITY = {"public", "private"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _today_prefix() -> str:
    return datetime.now(UTC).date().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(10)}"


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return data if isinstance(data, dict) else default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _empty_store() -> dict[str, Any]:
    return {
        "version": 1,
        "providers": {},
        "risk_policies": {},
        "subscriptions": {},
        "trade_events": {},
        "executions": {},
    }


def _load_store() -> dict[str, Any]:
    store = _read_json(PLATFORM_PATH, _empty_store())
    for key, default in _empty_store().items():
        if key == "version":
            store.setdefault(key, default)
        elif not isinstance(store.get(key), dict):
            store[key] = {}
    return store


def _save_store(store: dict[str, Any]) -> None:
    _write_json(PLATFORM_PATH, store)


def _normalize_symbol(symbol: Any) -> str:
    clean = str(symbol or "").strip().upper()
    if not clean:
        raise ValueError("Symbol is required")
    return clean


def _normalize_float(value: Any, *, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_take_profits(raw: Any) -> list[float]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",") if part.strip()]
    if not isinstance(raw, list | tuple):
        return []
    values: list[float] = []
    for item in raw:
        normalized = _normalize_float(item)
        if normalized is not None:
            values.append(normalized)
    return values


def _public_provider(provider: dict[str, Any]) -> dict[str, Any]:
    return dict(provider)


def _default_risk_policy(user_id: str) -> dict[str, Any]:
    now = _utc_now()
    return {
        "user_id": user_id,
        "paper_trading": True,
        "require_stop_loss": True,
        "allowed_symbols": [],
        "max_daily_loss": None,
        "max_open_trades": 100,
        "default_fixed_lot": 0.01,
        "updated_at": now,
        "created_at": now,
    }


def create_provider(owner_user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a signal/trader provider owned by a user."""
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Provider name is required")

    source_type = str(payload.get("source_type") or "manual").strip().lower()
    visibility = str(payload.get("visibility") or "public").strip().lower()
    if visibility not in _ALLOWED_VISIBILITY:
        raise ValueError("Visibility must be public or private")

    now = _utc_now()
    provider = {
        "id": _new_id("provider"),
        "owner_user_id": owner_user_id,
        "name": name,
        "source_type": source_type,
        "description": str(payload.get("description") or "").strip(),
        "visibility": visibility,
        "status": str(payload.get("status") or "active"),
        "created_at": now,
        "updated_at": now,
    }
    store = _load_store()
    store["providers"][provider["id"]] = provider
    _save_store(store)
    return _public_provider(provider)


def list_providers(user_id: str | None = None) -> list[dict[str, Any]]:
    """List public providers and private providers owned by the current user."""
    providers = []
    for provider in _load_store()["providers"].values():
        if not isinstance(provider, dict):
            continue
        if provider.get("visibility") == "public" or provider.get("owner_user_id") == user_id:
            providers.append(_public_provider(provider))
    return sorted(providers, key=lambda item: item.get("created_at") or "", reverse=True)


def get_provider(provider_id: str) -> dict[str, Any] | None:
    provider = _load_store()["providers"].get(provider_id)
    return _public_provider(provider) if isinstance(provider, dict) else None


def get_risk_policy(user_id: str) -> dict[str, Any]:
    policy = _load_store()["risk_policies"].get(user_id)
    if not isinstance(policy, dict):
        return _default_risk_policy(user_id)
    merged = _default_risk_policy(user_id)
    merged.update(policy)
    return merged


def upsert_risk_policy(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create or update a user's copy-trading risk policy."""
    store = _load_store()
    existing = store["risk_policies"].get(user_id)
    policy = _default_risk_policy(user_id)
    if isinstance(existing, dict):
        policy.update(existing)

    if "paper_trading" in payload:
        policy["paper_trading"] = bool(payload.get("paper_trading"))
    if "require_stop_loss" in payload:
        policy["require_stop_loss"] = bool(payload.get("require_stop_loss"))
    if "allowed_symbols" in payload:
        raw_symbols = payload.get("allowed_symbols") or []
        if isinstance(raw_symbols, str):
            raw_symbols = [part.strip() for part in raw_symbols.split(",") if part.strip()]
        policy["allowed_symbols"] = sorted({_normalize_symbol(symbol) for symbol in raw_symbols})
    if "max_daily_loss" in payload:
        max_daily_loss = _normalize_float(payload.get("max_daily_loss"))
        policy["max_daily_loss"] = max_daily_loss if max_daily_loss and max_daily_loss > 0 else None
    if "max_open_trades" in payload:
        max_open = int(_normalize_float(payload.get("max_open_trades"), default=10) or 10)
        policy["max_open_trades"] = max(1, max_open)
    if "default_fixed_lot" in payload:
        fixed_lot = _normalize_float(payload.get("default_fixed_lot"), default=0.01) or 0.01
        policy["default_fixed_lot"] = max(0.01, fixed_lot)

    policy["updated_at"] = _utc_now()
    store["risk_policies"][user_id] = policy
    _save_store(store)
    return dict(policy)


def create_subscription(follower_user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Subscribe a user to provider events."""
    store = _load_store()
    provider_id = str(payload.get("provider_id") or "").strip()
    provider = store["providers"].get(provider_id)
    if not isinstance(provider, dict):
        raise ValueError("Provider not found")
    if (
        provider.get("visibility") == "private"
        and provider.get("owner_user_id") != follower_user_id
    ):
        raise PermissionError("Provider is private")

    copy_mode = str(payload.get("copy_mode") or "fixed_lot").strip().lower()
    if copy_mode not in _ALLOWED_COPY_MODES:
        raise ValueError("Unsupported copy mode")

    fixed_lot = _normalize_float(payload.get("fixed_lot"), default=0.01) or 0.01
    multiplier = _normalize_float(payload.get("multiplier"), default=1.0) or 1.0
    now = _utc_now()

    # Update an existing subscription instead of creating duplicates for the same follower/provider.
    for subscription in store["subscriptions"].values():
        if (
            isinstance(subscription, dict)
            and subscription.get("follower_user_id") == follower_user_id
            and subscription.get("provider_id") == provider_id
        ):
            subscription.update(
                {
                    "copy_mode": copy_mode,
                    "fixed_lot": max(0.01, fixed_lot),
                    "multiplier": max(0.01, multiplier),
                    "paper_trading": True,
                    "status": str(payload.get("status") or "active"),
                    "updated_at": now,
                }
            )
            _save_store(store)
            return dict(subscription)

    subscription = {
        "id": _new_id("sub"),
        "provider_id": provider_id,
        "provider_name": provider.get("name"),
        "follower_user_id": follower_user_id,
        "copy_mode": copy_mode,
        "fixed_lot": max(0.01, fixed_lot),
        "multiplier": max(0.01, multiplier),
        "paper_trading": True,
        "status": str(payload.get("status") or "active"),
        "created_at": now,
        "updated_at": now,
    }
    store["subscriptions"][subscription["id"]] = subscription
    _save_store(store)
    return dict(subscription)


def list_subscriptions(user_id: str) -> list[dict[str, Any]]:
    subscriptions = [
        dict(subscription)
        for subscription in _load_store()["subscriptions"].values()
        if isinstance(subscription, dict) and subscription.get("follower_user_id") == user_id
    ]
    return sorted(subscriptions, key=lambda item: item.get("created_at") or "", reverse=True)


def create_trade_event(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a normalized trade event from a provider-owned source."""
    store = _load_store()
    provider_id = str(payload.get("provider_id") or "").strip()
    provider = store["providers"].get(provider_id)
    if not isinstance(provider, dict):
        raise ValueError("Provider not found")
    if provider.get("owner_user_id") != user_id:
        raise PermissionError("Only the provider owner can create events")

    action = str(payload.get("action") or "open").strip().lower()
    if action not in _ALLOWED_EVENT_ACTIONS:
        raise ValueError("Unsupported trade action")
    side = str(payload.get("side") or "").strip().lower()
    if action == "open" and side not in _ALLOWED_SIDES:
        raise ValueError("Side must be buy or sell for open events")

    symbol = _normalize_symbol(payload.get("symbol"))
    now = _utc_now()
    external_id = str(payload.get("external_id") or "").strip() or None
    if external_id:
        for existing in store["trade_events"].values():
            if (
                isinstance(existing, dict)
                and existing.get("provider_id") == provider_id
                and existing.get("external_id") == external_id
            ):
                return dict(existing)

    event = {
        "id": _new_id("event"),
        "provider_id": provider_id,
        "provider_name": provider.get("name"),
        "owner_user_id": user_id,
        "action": action,
        "symbol": symbol,
        "side": side or None,
        "entry_price": _normalize_float(payload.get("entry_price")),
        "stop_loss": _normalize_float(payload.get("stop_loss")),
        "take_profits": _normalize_take_profits(payload.get("take_profits")),
        "volume": _normalize_float(payload.get("volume")),
        "source": str(payload.get("source") or provider.get("source_type") or "manual"),
        "external_id": external_id,
        "status": "new",
        "created_at": now,
        "updated_at": now,
    }
    store["trade_events"][event["id"]] = event
    _save_store(store)
    return dict(event)


def list_trade_events(
    user_id: str | None = None,
    *,
    provider_id: str | None = None,
) -> list[dict[str, Any]]:
    store = _load_store()
    events = []
    for event in store["trade_events"].values():
        if not isinstance(event, dict):
            continue
        if provider_id and event.get("provider_id") != provider_id:
            continue
        if user_id and event.get("owner_user_id") != user_id:
            continue
        events.append(dict(event))
    return sorted(events, key=lambda item: item.get("created_at") or "", reverse=True)


def _daily_realized_loss(store: dict[str, Any], user_id: str) -> float:
    total = 0.0
    today = _today_prefix()
    for execution in store["executions"].values():
        if not isinstance(execution, dict):
            continue
        if execution.get("follower_user_id") != user_id:
            continue
        if not str(execution.get("created_at") or "").startswith(today):
            continue
        pnl = _normalize_float(execution.get("realized_pnl"), default=0.0) or 0.0
        if pnl < 0:
            total += abs(pnl)
    return total


def _open_trade_count(store: dict[str, Any], user_id: str) -> int:
    return sum(
        1
        for execution in store["executions"].values()
        if isinstance(execution, dict)
        and execution.get("follower_user_id") == user_id
        and execution.get("status") == "accepted"
        and execution.get("action") == "open"
    )


def _existing_execution(
    store: dict[str, Any], *, event_id: str, subscription_id: str
) -> dict[str, Any] | None:
    for execution in store["executions"].values():
        if (
            isinstance(execution, dict)
            and execution.get("event_id") == event_id
            and execution.get("subscription_id") == subscription_id
        ):
            return execution
    return None


def _risk_decision(
    store: dict[str, Any], event: dict[str, Any], subscription: dict[str, Any]
) -> tuple[bool, str | None]:
    policy = get_risk_policy(subscription["follower_user_id"])
    if (
        policy.get("require_stop_loss")
        and event.get("action") == "open"
        and not event.get("stop_loss")
    ):
        return False, "stop_loss_required"

    allowed_symbols = policy.get("allowed_symbols") or []
    if allowed_symbols and event.get("symbol") not in allowed_symbols:
        return False, "symbol_not_allowed"

    max_daily_loss = policy.get("max_daily_loss")
    if max_daily_loss and _daily_realized_loss(store, subscription["follower_user_id"]) >= float(
        max_daily_loss
    ):
        return False, "max_daily_loss_reached"

    max_open_trades = int(policy.get("max_open_trades") or 10)
    if (
        event.get("action") == "open"
        and _open_trade_count(store, subscription["follower_user_id"]) >= max_open_trades
    ):
        return False, "max_open_trades_reached"

    return True, None


def _execution_volume(event: dict[str, Any], subscription: dict[str, Any]) -> float:
    mode = subscription.get("copy_mode") or "fixed_lot"
    event_volume = _normalize_float(event.get("volume"), default=0.01) or 0.01
    if mode == "fixed_lot":
        return float(subscription.get("fixed_lot") or 0.01)
    if mode == "multiplier":
        return max(0.01, event_volume * float(subscription.get("multiplier") or 1.0))
    return max(0.01, event_volume)


def _create_execution(
    store: dict[str, Any],
    event: dict[str, Any],
    subscription: dict[str, Any],
    *,
    accepted: bool,
    reason: str | None,
) -> dict[str, Any]:
    now = _utc_now()
    execution = {
        "id": _new_id("exec"),
        "event_id": event["id"],
        "subscription_id": subscription["id"],
        "provider_id": event["provider_id"],
        "provider_name": event.get("provider_name"),
        "follower_user_id": subscription["follower_user_id"],
        "action": event.get("action"),
        "symbol": event.get("symbol"),
        "side": event.get("side"),
        "entry_price": event.get("entry_price"),
        "stop_loss": event.get("stop_loss"),
        "take_profits": event.get("take_profits") or [],
        "volume": _execution_volume(event, subscription),
        "mode": "paper" if subscription.get("paper_trading", True) else "live_pending",
        "status": "accepted" if accepted else "blocked",
        "blocked_reason": reason,
        "realized_pnl": 0.0,
        "created_at": now,
        "updated_at": now,
    }
    store["executions"][execution["id"]] = execution
    return execution


def process_trade_event(event_id: str) -> dict[str, Any]:
    """Apply all active subscriptions to one trade event in an idempotent way."""
    store = _load_store()
    event = store["trade_events"].get(event_id)
    if not isinstance(event, dict):
        raise ValueError("Trade event not found")

    created = 0
    blocked = 0
    skipped = 0
    results: list[dict[str, Any]] = []
    for subscription in list(store["subscriptions"].values()):
        if not isinstance(subscription, dict):
            continue
        if subscription.get("provider_id") != event.get("provider_id"):
            continue
        if subscription.get("status") != "active":
            continue

        existing = _existing_execution(
            store, event_id=event["id"], subscription_id=subscription["id"]
        )
        if existing:
            skipped += 1
            results.append(
                {
                    "subscription_id": subscription["id"],
                    "status": "skipped",
                    "reason": "already_processed",
                    "execution_id": existing["id"],
                }
            )
            continue

        accepted, reason = _risk_decision(store, event, subscription)
        execution = _create_execution(
            store, event, subscription, accepted=accepted, reason=reason
        )
        if accepted:
            created += 1
        else:
            blocked += 1
        results.append(
            {
                "subscription_id": subscription["id"],
                "status": execution["status"],
                "reason": reason,
                "execution_id": execution["id"],
            }
        )

    event["status"] = "processed"
    event["updated_at"] = _utc_now()
    _save_store(store)
    return {
        "event_id": event_id,
        "created": created,
        "blocked": blocked,
        "skipped": skipped,
        "results": results,
    }


def list_executions(
    user_id: str | None = None,
    *,
    provider_id: str | None = None,
) -> list[dict[str, Any]]:
    executions = []
    for execution in _load_store()["executions"].values():
        if not isinstance(execution, dict):
            continue
        if user_id and execution.get("follower_user_id") != user_id:
            continue
        if provider_id and execution.get("provider_id") != provider_id:
            continue
        executions.append(dict(execution))
    return sorted(executions, key=lambda item: item.get("created_at") or "", reverse=True)


def platform_overview(user_id: str) -> dict[str, Any]:
    store = _load_store()
    providers = list_providers(user_id)
    subscriptions = list_subscriptions(user_id)
    executions = list_executions(user_id)
    owned_provider_ids = {
        provider["id"] for provider in providers if provider.get("owner_user_id") == user_id
    }
    owned_events = [
        event
        for event in store["trade_events"].values()
        if isinstance(event, dict) and event.get("provider_id") in owned_provider_ids
    ]
    return {
        "providers": providers,
        "subscriptions": subscriptions,
        "risk_policy": get_risk_policy(user_id),
        "recent_events": sorted(
            owned_events,
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )[:20],
        "recent_executions": executions[:20],
        "metrics": {
            "provider_count": len(owned_provider_ids),
            "available_provider_count": len(providers),
            "subscription_count": len(subscriptions),
            "paper_execution_count": sum(
                1 for item in executions if item.get("mode") == "paper"
            ),
            "blocked_execution_count": sum(
                1 for item in executions if item.get("status") == "blocked"
            ),
        },
    }


def run_stress_test(user_id: str, provider_id: str, *, count: int = 100) -> dict[str, Any]:
    """Generate and process a burst of paper events for local/browser stress testing."""
    count = max(1, min(int(count), 500))
    start = time.perf_counter()
    executions_created = 0
    blocked = 0
    skipped = 0
    event_ids: list[str] = []
    for index in range(count):
        side = "buy" if index % 2 == 0 else "sell"
        entry = 2350.0 + (index * 0.1)
        event = create_trade_event(
            user_id,
            {
                "provider_id": provider_id,
                "action": "open",
                "symbol": "XAUUSD",
                "side": side,
                "entry_price": entry,
                "stop_loss": entry - 10 if side == "buy" else entry + 10,
                "take_profits": [entry + 15 if side == "buy" else entry - 15],
                "volume": 0.01,
                "source": "stress_test",
            },
        )
        event_ids.append(event["id"])
        result = process_trade_event(event["id"])
        executions_created += int(result["created"])
        blocked += int(result["blocked"])
        skipped += int(result["skipped"])

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        "events": count,
        "event_ids": event_ids,
        "executions_created": executions_created,
        "blocked": blocked,
        "skipped": skipped,
        "duration_ms": duration_ms,
    }
