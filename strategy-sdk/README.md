# Trading Strategy SDK

`trading-strategy-sdk` is the typed contract package for Release 1 strategies. It defines
validated strategy specifications, deterministic closed-bar inputs, explicit JSON state,
MT5-compatible order constants, position snapshots, managed-order policies, and strategy
intents. It requires Python 3.12 or newer.

The package intentionally contains no broker adapter, account access, sizing, risk engine,
fill simulator, backtest engine, or runtime. A strategy can emit technical prices and relative
close fractions; the Platform alone chooses accounts and final volume under the user's risk
policy.

## Contract boundaries

- `StrategySpec` declares every symbol/timeframe subscription, warmup, trigger, synchronization
  requirement, rule, parameter, position mode, capability, order/filling type, exact dependency,
  disclosure, and bounded-loss requirement.
- `StrategyContext` contains only finite, already-materialized snapshots as of the triggering
  bar's `close_time`, including positions, pending orders, OCO groups, managed exit plans, and
  typed placement/lifecycle results. Position snapshots intentionally omit platform-resolved
  volume at every nesting level. Missing, stale, or insufficiently warmed data blocks new
  entries while leaving protective exits eligible.
- `StrategyState` accepts portable JSON objects only, recursively rejects account-risk,
  credential, and sizing aliases, and bounds canonical bytes, nesting depth, and cumulative
  items before serializing to canonical JSON.
- MT5's complete order, action, expiration, and filling enum families retain their native integer
  values. FOK, IOC, and BOC specifications require the depth-of-market capability.
- `OrderIntent` is a closed discriminated union. Its models reject unknown fields and have no
  final lot, volume, account balance, credentials, leverage, allocation, or user-risk-policy
  field. `StrategyOutput` closes the signals/intents/next-state boundary; platform boundaries
  must pass it through `validate_strategy_output(..., spec=..., context=...)`. Individual
  intents can use the same semantic checks through `validate_order_intent` with both arguments.
- Context-aware validation places BUY limits and SELL stops at or below the current Ask/Bid,
  respectively, and SELL limits and BUY stops at or above the current Bid/Ask. Stop-limit trigger
  prices use the corresponding stop boundary; equality is valid.
- Every immutable SDK contract exposes `canonical_bytes()` and `sha256_digest()`. The module-level
  `canonical_bytes(contract)` and `sha256_digest(contract)` APIs are equivalent. Canonical JSON is
  compact UTF-8 with lexically sorted object keys and a lowercase `sha256:<hex>` identity.
  Semantically unordered spec collections (subscriptions, warmup, triggers, parameters,
  dependencies, capabilities, order types, filling policies, and dependency hashes) are
  normalized. Entry rules, exit rules, and disclosures retain their declared order because their
  evaluation/presentation order is contract-significant.
- `LifecycleResult` is a closed discriminated union for order modification/removal, protection,
  full and partial close, close-by, OCO modification/cancellation, and managed-exit
  modification/clearing. Rejected and failed variants carry only bounded, redacted summaries and
  operation-correct target IDs; they never carry broker payloads or resolved volume.

`DependencySpec` represents the resolved, immutable dependency record (canonical PEP 440 version
and SHA-256 artifact hashes), not the user's unresolved package request.

## Development

```bash
uv sync --frozen
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run pyright
```
