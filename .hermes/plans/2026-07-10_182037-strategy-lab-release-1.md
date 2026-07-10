# Strategy Lab Release 1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task, with spec-compliance review followed by code-quality review for every milestone.

**Goal:** Build and deploy a public, open-source Python Strategy Lab where verified users describe multi-symbol/multi-timeframe strategies in chat, Codex generates versioned code, the platform validates and backtests it, and users run it on an automatically created $500 paper account.

**Architecture:** Replace JSON persistence and Clerk with PostgreSQL + Better Auth, ingest Dukascopy M1 Bid/Ask into versioned Parquet datasets, execute untrusted strategies in gVisor sandboxes, and keep strategy logic separate from user-owned risk/execution policies. Release 1 is strictly paper-only; MT5 is used only as an independent data-validation source.

**Tech Stack:** FastAPI, Python 3.12+, SQLAlchemy 2 async, Alembic, PostgreSQL, Polars/PyArrow, Next.js 16, Better Auth, Bun, TypeScript, Codex SDK/App Server, gVisor `runsc`, Stalwart Mail Server, pytest, Ruff, Pyright, Vitest, Playwright, Dokploy.

---

## 1. Locked product decisions

| Area | Decision |
|---|---|
| Release sequencing | R1 Strategy Lab + Paper; R2 managed MT5 real/demo execution; R3 native MQL5 |
| Builder UX | Chat-only; structured spec remains server-side |
| Strategy runtime | Python bar-close in R1; M5 minimum |
| Market universe | XAUUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD |
| Data scope | Multi-symbol + multi-timeframe |
| Canonical market data | Dukascopy M1 Bid/Ask, aggregated by Platform |
| MT5 role in R1 | Independent validation only; never silent runtime fallback |
| Backtest | Development + chronological out-of-sample + sealed benchmark |
| Paper account | Auto-created, $500 USD, allocations cannot exceed available balance |
| Reset semantics | New immutable season; no history deletion |
| Risk ownership | User/Platform policy only; strategy cannot set final lot/risk |
| Default risk | 1% per trade, 3% total open risk, 5% daily loss, 20% drawdown, 1:100, max 5 trades |
| Position model | Creator chooses netting or hedging per immutable version |
| Order model | All MT5 order/action/expiration types plus platform-managed OCO/trailing/partials |
| DOM-dependent fills | FOK/IOC/BOC rejected in standard benchmark without depth data |
| Dependencies | Any PyPI package may be requested; exact lock/hash, isolated build, mandatory scans |
| Sandbox | gVisor on current server; no KVM/Firecracker available there |
| Public source | Fully downloadable/open-source |
| License | Apache-2.0 default; MIT/GPL-3.0/AGPL-3.0 selectable |
| Collaboration | Issues, forks, natural-language/manual change proposals, immutable versions |
| Publishing | First public version needs Admin review; later compatible versions auto-publish after automated gates |
| Upgrades | Existing activations remain pinned until user approves an upgrade |
| Real execution policy | Future users may opt into real with warnings; security/risk gates remain mandatory |
| Codex auth | Shared non-API Codex subscription, global FIFO queue |
| Codex budget | Platform may consume at most 10 percentage points per weekly window; 8% operational soft stop |
| Signup | Open signup; default role `trader`; verified email required |
| Auth | Replace Clerk with Better Auth, PostgreSQL-backed |
| Email | Self-host Stalwart on current Dokploy server |
| Mail identity | `mail.kiaparsaprintingmoneymachine.cloud`; sender `no-reply@kiaparsaprintingmoneymachine.cloud` |
| Deployment | Dokploy on `168.231.106.125`; existing API/dashboard domains retained |

## 2. Explicit non-goals for Release 1

- No new live/demo MT5 strategy activation.
- No broker credential provisioning.
- No MQL5 generation, MetaEditor compile, Strategy Tester, or native EA runtime.
- No tick/scalping strategy support below M5.
- No market-depth-accurate FOK/IOC/BOC simulation.
- No paid strategy subscriptions, billing, or creator revenue share.
- No cross-provider raw market-data redistribution/download.
- No auto-upgrade of follower activations.
- No arbitrary network, filesystem, subprocess, Docker socket, database, or secret access from strategy code.

## 3. Release gates and external prerequisites

Open signup and public publishing must remain feature-flagged off until all applicable gates pass:

1. Hostinger PTR is manually set to `mail.kiaparsaprintingmoneymachine.cloud`.
2. Forward A, PTR, SPF, DKIM, DMARC, MX, SMTP TLS, Gmail/Outlook/Yahoo placement tests pass.
3. gVisor is installed as an additional Docker runtime and a sandbox-escape regression suite passes.
4. A dedicated persistent `CODEX_HOME` is device-authenticated on the server.
5. Shared-subscription end-user use is confirmed compatible with current OpenAI/Codex terms; otherwise keep Builder owner-only or change auth backend without changing the queue interface.
6. Dukascopy multi-user/derived-display use is confirmed before commercial public launch; private beta may proceed with source labeling and no raw-data redistribution.
7. PostgreSQL backups and restore drill pass.
8. Existing Clerk users and JSON-backed domain state are migrated and reconciled.

---

# Implementation milestones

## Milestone 0 — Baseline, branch, backups, and feature flags

### Task 0.1: Capture baseline and create the feature branch

**Files:** No code changes.

**Steps:**
1. Verify `main` remains clean at commit `94edfec` or record the newer baseline.
2. Run existing API, bot, dashboard lint/build/test commands and save output under `.hermes/evidence/baseline/`.
3. Create `feat/strategy-lab-release-1`.
4. Export/backup Dokploy application configuration and persistent `/app/data` without printing secrets.
5. Record rollback commit and current deployed image IDs.

**Verification:** Existing production health, API, dashboard, bot, MT5 runtime, and WebSockets still behave exactly as before.

### Task 0.2: Add dark-launch feature flags

**Files:**
- Modify: `api/src/config.py`
- Modify: `api/.env.example`
- Modify: `dashboard/src/lib/constants.ts`
- Modify: `Dockerfile`
- Test: `api/tests/test_feature_flags.py`

**Flags:**
- `STRATEGY_LAB_ENABLED=false`
- `OPEN_SIGNUP_ENABLED=false`
- `CODEX_BUILDER_ENABLED=false`
- `PAPER_LIVE_ENABLED=false`
- `PUBLIC_STRATEGY_PUBLISHING_ENABLED=false`

**Verification:** All old routes work while all new pages/routes return a controlled disabled state.

---

## Milestone 1 — PostgreSQL foundation and migration from JSON/SQLite

### Task 1.1: Add async PostgreSQL infrastructure

**Files:**
- Modify: `api/pyproject.toml`
- Modify: `api/uv.lock`
- Create: `api/src/db/base.py`
- Create: `api/src/db/session.py`
- Create: `api/src/db/health.py`
- Create: `api/alembic.ini`
- Create: `api/alembic/env.py`
- Create: `api/alembic/versions/0001_app_schema.py`
- Test: `api/tests/db/test_database.py`

**Dependencies:** SQLAlchemy 2, asyncpg, Alembic.

**Requirements:**
- Use PostgreSQL schema `app` for FastAPI-owned tables.
- Better Auth tables live separately and are not mutated directly by FastAPI migrations.
- No schema creation through app startup in production; Alembic is the source of truth.
- Add pool health, timeout, and graceful shutdown.

**TDD:** Test transaction rollback, connection failure, health response, and migration up/down on a disposable PostgreSQL database.

### Task 1.2: Model app users, accounts, and audit events

**Files:**
- Create: `api/src/models/user.py`
- Create: `api/src/models/account.py`
- Create: `api/src/models/audit.py`
- Create: `api/src/repositories/users.py`
- Create: `api/src/repositories/accounts.py`
- Test: `api/tests/repositories/test_users.py`
- Test: `api/tests/repositories/test_accounts.py`

**Tables:**
- `app_user_profiles`
- `trading_accounts`
- `account_memberships`
- `audit_events`
- `legacy_identity_aliases`

**Rules:** Stable Better Auth `sub` is the identity key. Roles are `owner/admin/trader/viewer`; public signup defaults to `trader`. MT5 credentials stay encrypted and are never returned by APIs.

### Task 1.3: Migrate existing JSON/SQLite state idempotently

**Files:**
- Create: `api/scripts/migrate_json_to_postgres.py`
- Create: `api/src/migrations/legacy_import.py`
- Test: `api/tests/migrations/test_legacy_import.py`

**Inputs:** Existing access, account, platform, runtime, and trade-history stores.

**Rules:**
- Dry-run mode is mandatory.
- Re-running produces no duplicates.
- Every imported object records legacy source and ID.
- Secret-bearing fields are encrypted before insert and redacted in logs.
- Emit counts/checksums, not values.
- Do not delete legacy files until post-cutover verification and a retained backup exist.

---

## Milestone 2 — Better Auth replacement for Clerk

### Task 2.1: Install and configure Better Auth

**Files:**
- Modify: `dashboard/package.json`
- Modify: `dashboard/bun.lock`
- Create: `dashboard/src/lib/auth.ts`
- Create: `dashboard/src/lib/auth-client.ts`
- Create: `dashboard/src/app/api/auth/[...all]/route.ts`
- Create: `dashboard/src/lib/auth/permissions.ts`
- Create: `dashboard/src/lib/auth/email.ts`
- Test: `dashboard/src/lib/auth/auth.test.ts`

**Plugins/features:** Email/password, required email verification, JWT/JWKS, Admin/custom roles, Captcha, rate limiting; passkey can be enabled after base cutover.

**Security:**
- Default role `trader` is server-assigned.
- Session cookies are HttpOnly/Secure/SameSite.
- JWT audience is the FastAPI service and lifetime is short.
- JWT payload includes stable subject, verified email, role, issuer, audience, expiration.
- JWT remains memory-only in the browser.
- Better Auth secret is generated, stored only in Dokploy secrets, and never committed.

### Task 2.2: Replace Clerk pages and middleware

**Files:**
- Replace: `dashboard/src/app/sign-in/[[...sign-in]]/page.tsx`
- Replace: `dashboard/src/app/sign-up/[[...sign-up]]/page.tsx`
- Create: `dashboard/src/app/forgot-password/page.tsx`
- Create: `dashboard/src/app/reset-password/page.tsx`
- Create: `dashboard/src/app/verify-email/page.tsx`
- Modify: `dashboard/src/proxy.ts`
- Modify: `dashboard/src/app/layout.tsx`
- Delete after cutover: `dashboard/src/components/auth/clerk-root-provider.tsx`
- Delete after cutover: `dashboard/src/lib/clerk-token.ts`
- Test: `dashboard/e2e/auth.spec.ts`

**Verification:** Signup, verification, login, logout, reset, session expiry, protected routing, role denial, and captcha all work.

### Task 2.3: Validate Better Auth JWTs in FastAPI

**Files:**
- Create: `api/src/auth/better_auth.py`
- Create: `api/src/auth/models.py`
- Modify: `api/src/security.py`
- Modify: `api/src/dependencies.py`
- Modify: `api/src/routers/auth.py`
- Test: `api/tests/auth/test_better_auth.py`

**Validation:** Fixed algorithm allowlist, signature, `iss`, `aud`, `exp`, `nbf`, verified email, role, active app profile. Cache JWKS with bounded refresh and rotation handling.

### Task 2.4: Add one-time WebSocket tickets

**Files:**
- Create: `api/src/auth/ws_tickets.py`
- Create: `api/src/routers/ws_auth.py`
- Modify: `api/src/main.py`
- Modify: `dashboard/src/hooks/use-websocket.ts`
- Test: `api/tests/auth/test_ws_tickets.py`
- Test: `dashboard/e2e/websocket-auth.spec.ts`

**Rules:** Ticket is opaque, single-use, account/user-bound, and expires in about 30 seconds. Bearer JWTs must not appear in WebSocket URLs or logs.

### Task 2.5: Remove Clerk only after verified cutover

**Files:**
- Remove Clerk dependency from `dashboard/package.json`
- Delete: `api/src/clerk_client.py`
- Remove Clerk branches/fields from `api/src/security.py`, `api/src/access_store.py`, `api/src/routers/access.py`, `dashboard/src/lib/api.ts`, `dashboard/src/types/index.ts`
- Remove Clerk build args from `Dockerfile`
- Replace Clerk env docs in `api/.env.example`

**Verification:** Repository-wide search finds no active Clerk import, secret, env, claim, route, or UI dependency. Existing migrated users can reset credentials and owner access remains available.

---

## Milestone 3 — Stalwart transactional mail

### Task 3.1: Add local Mailpit and production Stalwart definitions

**Files:**
- Create: `infra/local/compose.yaml`
- Create: `infra/stalwart/compose.yaml`
- Create: `infra/stalwart/README.md`
- Create: `infra/stalwart/config.example.toml`
- Create: `infra/stalwart/dns-check.sh`

**Rules:**
- Production secrets are Dokploy-only.
- SMTP submission is internal/authenticated; no open relay.
- Public SMTP port 25 and HTTPS admin are exposed intentionally; admin requires strong auth.
- Persistent queue/config/data volumes are backed up.
- Only transactional/auth mail is permitted.

### Task 3.2: Configure DNS and PTR gate

**Manual prerequisites:**
- A: `mail.kiaparsaprintingmoneymachine.cloud -> 168.231.106.125`
- PTR: `168.231.106.125 -> mail.kiaparsaprintingmoneymachine.cloud`
- SPF, DKIM, DMARC, MX, TLS/STARTTLS.

**Verification commands:** `dig`, `openssl s_client -starttls smtp`, `swaks`, real Gmail/Outlook/Yahoo deliveries, SPF/DKIM/DMARC header checks, bounce and reset-email tests.

**Go-live rule:** `OPEN_SIGNUP_ENABLED` cannot become true until this task passes.

---

## Milestone 4 — Automatic paper account and user-owned risk

### Task 4.1: Create paper account schema and provisioning service

**Files:**
- Create: `api/src/models/paper.py`
- Create: `api/src/services/paper_accounts.py`
- Create: `api/src/repositories/paper.py`
- Create migration: `api/alembic/versions/0002_paper_accounts.py`
- Test: `api/tests/services/test_paper_accounts.py`

**Tables:** `paper_accounts`, `paper_seasons`, `paper_ledger_entries`, `paper_allocations`, `paper_equity_snapshots`.

**Invariants:**
- Exactly one active paper account per user.
- Initial credit is exactly USD 500.
- Provisioning is idempotent and runs after signup plus on first authenticated API request as fallback.
- Allocations cannot exceed available equity.
- Reset archives the old season and creates a new one; it never deletes history.

### Task 4.2: Implement account and activation risk policies

**Files:**
- Create: `api/src/models/risk.py`
- Create: `api/src/services/risk_engine.py`
- Create: `api/src/repositories/risk.py`
- Test: `api/tests/services/test_risk_engine.py`
- Add property tests: `api/tests/property/test_risk_invariants.py`

**Defaults:** 1% per trade, 3% total open risk, 5% daily loss, 20% drawdown, 1:100, maximum five simultaneous trades, SL required by default.

**Invariants:** Strategy code cannot supply final lot. Effective activation policy is never less restrictive than account policy. Volume rounds down to instrument step; a minimum lot that violates risk rejects the signal.

---

## Milestone 5 — Strategy repository, immutable versions, and collaboration

### Task 5.1: Create strategy domain schema

**Files:**
- Create: `api/src/models/strategy.py`
- Create: `api/src/repositories/strategies.py`
- Create migration: `api/alembic/versions/0003_strategies.py`
- Test: `api/tests/repositories/test_strategies.py`

**Tables:**
- `strategies`, `strategy_maintainers`, `strategy_versions`, `strategy_files`
- `strategy_dependencies`, `strategy_artifacts`, `strategy_drafts`, `strategy_candidates`
- `strategy_forks`, `strategy_issues`, `strategy_change_proposals`, `strategy_proposal_comments`
- `strategy_reviews`, `strategy_official_tracks`

**Invariants:** Versions/files/artifact hashes are immutable. Public removal archives listing but cannot revoke an already granted open-source license. Visibility defaults private.

### Task 5.2: Implement licensing and provenance

**Files:**
- Create: `api/src/services/strategy_licenses.py`
- Create: `api/src/services/strategy_bundles.py`
- Test: `api/tests/services/test_strategy_licenses.py`
- Test: `api/tests/services/test_strategy_bundles.py`

**Allowed licenses:** Apache-2.0 default, MIT, GPL-3.0, AGPL-3.0. Proposal contributors explicitly license contributions under the current strategy license. Download bundle includes source, manifest, parameter schema, tests, README, changelog, LICENSE, lockfile, hashes, SBOM, and provenance.

### Task 5.3: Implement review and publishing lifecycle

**Files:**
- Create: `api/src/services/strategy_publishing.py`
- Test: `api/tests/services/test_strategy_publishing.py`

**Lifecycle:** DRAFT -> SPEC_CONFIRMED -> GENERATED -> VALIDATED -> BACKTESTED -> REVIEW_PENDING -> PUBLISHED; paper/live statuses remain separate.

**Rules:** First public version needs owner/admin approval. Later compatible versions auto-publish only after automated gates. Runtime/capability/dependency/license/ownership escalation re-enters manual review. Running activations stay pinned.

---

## Milestone 6 — Market-data ingestion and versioned datasets

### Task 6.1: Create provider abstraction and instrument catalog

**Files:**
- Create: `api/src/market_data/types.py`
- Create: `api/src/market_data/provider.py`
- Create: `api/src/market_data/instruments.py`
- Create: `api/src/market_data/providers/dukascopy.py`
- Create: `api/src/market_data/providers/mt5_validation.py`
- Test: `api/tests/market_data/test_dukascopy_provider.py`
- Fixtures: `api/tests/fixtures/dukascopy/`

**Scope:** Six approved symbols, UTC, M1 Bid/Ask canonical data. Higher timeframes are never trusted from the upstream real-time endpoint; aggregate locally.

### Task 6.2: Add partitioned Parquet storage and metadata

**Files:**
- Create: `api/src/market_data/storage.py`
- Create: `api/src/models/dataset.py`
- Create migration: `api/alembic/versions/0004_datasets.py`
- Create: `api/src/workers/market_data_worker.py`
- Test: `api/tests/market_data/test_storage.py`

**Layout:** `provider/symbol/year/month/side/*.parquet`. PostgreSQL stores dataset/partition manifests, checksums, coverage, quality reports, split metadata, and provenance. Raw data is not included in public strategy downloads.

### Task 6.3: Validate and aggregate market data

**Files:**
- Create: `api/src/market_data/quality.py`
- Create: `api/src/market_data/aggregate.py`
- Test: `api/tests/market_data/test_quality.py`
- Test: `api/tests/market_data/test_aggregate.py`

**Checks:** Duplicates, monotonicity, missing intervals, expected weekend/holiday gaps, OHLC validity, Ask >= Bid, spread spikes, return outliers, checksum, MT5 sample comparison.

**Live safety:** A stale/incomplete feed pauses new paper entries; protective exits continue. No silent provider switch.

### Task 6.4: Build chronological dataset splits

**Files:**
- Create: `api/src/market_data/splits.py`
- Test: `api/tests/market_data/test_splits.py`

**Default split:** 60% development, 20% out-of-sample validation, 20% sealed benchmark by chronological time. Split definitions are versioned. Sealed raw data is inaccessible to Codex/Builder and runs only against a candidate artifact hash.

---

## Milestone 7 — Strategy specification and SDK

### Task 7.1: Define the hidden structured StrategySpec

**Files:**
- Create: `strategy-sdk/pyproject.toml`
- Create: `strategy-sdk/src/trading_strategy_sdk/spec.py`
- Create: `strategy-sdk/tests/test_spec.py`

**Fields:** symbols, timeframes, warmup, triggers/synchronization, entries/exits, parameters, netting/hedging mode, required capabilities, order types, dependencies, disclosures, and bounded-loss requirements.

### Task 7.2: Define deterministic event/context APIs

**Files:**
- Create: `strategy-sdk/src/trading_strategy_sdk/context.py`
- Create: `strategy-sdk/src/trading_strategy_sdk/events.py`
- Create: `strategy-sdk/src/trading_strategy_sdk/state.py`
- Test: `strategy-sdk/tests/test_no_lookahead.py`

**Rules:** Only closed bars with `close_time <= event_time` are visible. Event ordering is deterministic. Incomplete multi-symbol snapshots skip new entries. State is explicit and serializable.

### Task 7.3: Implement full order and position API

**Files:**
- Create: `strategy-sdk/src/trading_strategy_sdk/orders.py`
- Create: `strategy-sdk/src/trading_strategy_sdk/positions.py`
- Test: `strategy-sdk/tests/test_orders.py`
- Test: `strategy-sdk/tests/test_position_modes.py`

**Order support:** BUY/SELL, limits, stops, stop-limits, close-by, modify/cancel, SL/TP, GTC/DAY/SPECIFIED/SPECIFIED_DAY, plus OCO/brackets/trailing/break-even/partials. FOK/IOC/RETURN/BOC remain capability-declared; DOM-dependent modes fail standard benchmark without depth.

### Task 7.4: Enforce strategy/risk separation

**Files:**
- Create: `strategy-sdk/src/trading_strategy_sdk/intents.py`
- Test: `strategy-sdk/tests/test_no_direct_volume.py`

**Rule:** Strategies emit signal/order intents and technical prices, never final lot, account balance, credentials, or user policy changes.

---

## Milestone 8 — gVisor sandbox and arbitrary PyPI build pipeline

### Task 8.1: Install gVisor as an additional runtime

**Files:**
- Create: `infra/gvisor/install.sh`
- Create: `infra/gvisor/verify.sh`
- Create: `infra/gvisor/rollback.md`

**Procedure:** Back up Docker daemon config, install pinned official `runsc`, register it without changing default runtime, perform controlled Docker restart, verify all existing Dokploy workloads, and run a gVisor smoke container.

**Rollback:** Restore daemon config/package and restart Docker. This task requires a maintenance window and must not be automated blindly.

### Task 8.2: Create a narrow host sandbox manager

**Files:**
- Create: `sandbox-manager/go.mod`
- Create: `sandbox-manager/cmd/sandbox-manager/main.go`
- Create: `sandbox-manager/internal/policy/policy.go`
- Create: `sandbox-manager/internal/runner/runner.go`
- Create: `sandbox-manager/internal/jobs/jobs.go`
- Create: `sandbox-manager/systemd/sandbox-manager.service`
- Test: `sandbox-manager/internal/policy/policy_test.go`
- Test: `sandbox-manager/internal/runner/runner_integration_test.go`

**Rules:** The public API never receives Docker socket access. The manager accepts only fixed signed job schemas from a private Unix socket or DB queue; it owns all runtime options and never accepts arbitrary images, mounts, commands, networks, or capabilities.

### Task 8.3: Implement dependency resolution/build sandbox

**Files:**
- Create: `api/src/sandbox/dependencies.py`
- Create: `api/src/sandbox/artifacts.py`
- Create: `sandbox-images/python-bar-v1/Dockerfile`
- Test: `api/tests/sandbox/test_dependencies.py`
- Test: `api/tests/sandbox/test_malicious_packages.py`

**Rules:** PyPI only; exact transitive lock and hashes; wheel preferred; sdists/build scripts remain inside disposable gVisor build sandbox; network only through an allowlisted package-download path; runtime network is none. Generate SBOM, license scan, OSV/pip-audit report, import/resource smoke tests, and artifact digest. A requested package may be rejected.

### Task 8.4: Enforce runtime containment

**Required runtime options:** `runsc`, non-root, read-only rootfs, no capabilities, no-new-privileges, network none, bounded tmpfs, bounded CPU/RAM/PIDs/output/time, no host/device/secret mounts.

**Tests:** Attempt file escape, network access, fork bomb, memory bomb, infinite loop, subprocess, environment reads, Docker socket access, and cross-job state leakage. All must fail safely without host impact.

---

## Milestone 9 — Codex builder and global subscription quota

### Task 9.1: Add dedicated Node builder worker

**Files:**
- Create: `strategy-builder/package.json`
- Create: `strategy-builder/src/worker.ts`
- Create: `strategy-builder/src/codex.ts`
- Create: `strategy-builder/src/prompts/strategy-system.md`
- Create: `strategy-builder/src/schema.ts`
- Test: `strategy-builder/src/worker.test.ts`
- Modify: `Dockerfile` with a separate `strategy-builder` target

**Rules:** Dedicated persistent `CODEX_HOME`, device auth only on server, one global Codex job at a time, no MT5/user secrets, workspace limited to one draft/candidate, structured outputs validated before persistence.

### Task 9.2: Implement rate-limit and 10-point weekly budget guard

**Files:**
- Create: `strategy-builder/src/rate-limits.ts`
- Create: `api/src/models/codex_usage.py`
- Create: `api/src/services/codex_quota.py`
- Create migration: `api/alembic/versions/0005_codex_jobs.py`
- Test: `strategy-builder/src/rate-limits.test.ts`
- Test: `api/tests/services/test_codex_quota.py`

**Tables:** `codex_quota_windows`, `codex_jobs`, `codex_usage_events`.

**Policy:** FIFO, one active job/user, bounded queued jobs/user, no weekly user allocation, 10 percentage-point maximum attributed to Platform, 8% operational soft stop, current 5-hour window also respected, reset detected by `resetsAt`. External concurrent usage is conservatively attributed during a Platform job.

### Task 9.3: Implement conversational spec/generation workflow

**Files:**
- Create: `api/src/models/strategy_generation.py`
- Create: `api/src/services/strategy_generation.py`
- Create: `api/src/routers/strategy_builder.py`
- Test: `api/tests/services/test_strategy_generation.py`

**Flow:** Idea -> clarification -> hidden structured spec -> user summary confirmation -> candidate generation -> sandbox validation/tests -> change request/diff -> backtest -> immutable version. Drafts resume after browser close; Codex thread IDs are references, never the only source of truth.

---

## Milestone 10 — Deterministic backtest engine

### Task 10.1: Build event timeline and synchronization

**Files:**
- Create: `api/src/backtest/timeline.py`
- Create: `api/src/backtest/synchronizer.py`
- Test: `api/tests/backtest/test_timeline.py`
- Test: `api/tests/backtest/test_multisymbol_sync.py`

**Rules:** Merge all subscribed symbol/timeframe events deterministically; only closed data; warmup respected; missing snapshots block entries and record `data_incomplete`.

### Task 10.2: Build fill/order simulator

**Files:**
- Create: `api/src/execution/orders.py`
- Create: `api/src/execution/fills.py`
- Create: `api/src/execution/positions.py`
- Test: `api/tests/execution/test_order_types.py`
- Test: `api/tests/execution/test_netting.py`
- Test: `api/tests/execution/test_hedging.py`

**Rules:** Use Bid/Ask correctly by side, fill post-signal at next tradable quote/bar, support selected MT5 semantics and platform-managed orders, and record every decision. Same-M1 SL/TP ambiguity uses a conservative deterministic path and increments an `intrabar_ambiguity` metric.

### Task 10.3: Build benchmark and metrics

**Files:**
- Create: `api/src/backtest/engine.py`
- Create: `api/src/backtest/metrics.py`
- Create: `api/src/models/backtest.py`
- Create migration: `api/alembic/versions/0006_backtests.py`
- Test: `api/tests/backtest/test_engine.py`
- Golden tests: `api/tests/backtest/golden/`

**Runs:** Development, validation, sealed benchmark, custom. Standard profile uses $500 and locked risk defaults. Costs are versioned and include observed Bid/Ask plus an explicit commission/slippage/swap model; reports must never hide unmodeled costs.

**Metrics:** Return, drawdown, equity, profit factor, expectancy, win rate, trade count, exposure, turnover, per-symbol attribution, rejected signals, data gaps, ambiguous fills, stress sensitivity.

### Task 10.4: Prevent sealed-data leakage

Codex/Builder and user sandboxes cannot read sealed partitions. Backtest worker provides only aggregate result for a finalized artifact hash. Every submission remains in internal audit history.

---

## Milestone 11 — Paper execution and official forward tracks

### Task 11.1: Create paper order/position/deal schema

**Files:**
- Extend: `api/src/models/paper.py`
- Create migration: `api/alembic/versions/0007_paper_execution.py`
- Test: `api/tests/services/test_paper_execution.py`

**Tables:** `strategy_activations`, `paper_orders`, `paper_positions`, `paper_deals`, `paper_execution_events`, `paper_track_metrics`.

### Task 11.2: Reuse backtest execution semantics in live paper

**Files:**
- Create: `api/src/services/paper_execution.py`
- Create: `api/src/workers/paper_worker.py`
- Test: `api/tests/integration/test_backtest_paper_parity.py`

**Invariant:** Given identical events/quotes, backtest and paper produce the same order/risk decisions. Strategy runners never connect to brokers or market-data providers directly.

### Task 11.3: Start official immutable tracks for public versions

Every published version gets a separate standardized $500 forward track. Personal paper results remain private and use user policies; Marketplace displays the official track. Version histories and bad periods cannot be reset or selectively deleted.

---

## Milestone 12 — APIs and authorization

### Task 12.1: Add Strategy/Marketplace APIs

**Files:**
- Create: `api/src/routers/strategies.py`
- Create: `api/src/routers/strategy_versions.py`
- Create: `api/src/routers/backtests.py`
- Create: `api/src/routers/paper.py`
- Create: `api/src/routers/strategy_collaboration.py`
- Create: `api/src/routers/strategy_reviews.py`
- Modify: `api/src/main.py`
- Test: `api/tests/api/test_strategy_api.py`
- Test: `api/tests/api/test_authorization_matrix.py`

**Authorization:** Viewer reads public artifacts; trader creates/forks/proposes/backtests/activates paper; owner/admin review/suspend/manage. Private source is owner/maintainer-only. Object-level authorization is mandatory.

### Task 12.2: Integrate, do not overwrite, existing Platform domain

**Files:**
- Refactor: `api/src/platform_store.py`
- Refactor: `api/src/routers/platform.py`
- Preserve/update: `api/tests/test_platform_store.py`
- Preserve/update: `api/tests/test_platform_api.py`

Migrate existing providers/subscriptions/events/executions to repositories. Add `strategy` as a provider/source type without breaking manual/webhook/Telegram/MT5 mirror paths. Preserve the existing paper-only guard in R1.

---

## Milestone 13 — Dashboard UX

### Task 13.1: Add frontend test infrastructure

**Files:**
- Modify: `dashboard/package.json`
- Create: `dashboard/vitest.config.ts`
- Create: `dashboard/playwright.config.ts`
- Create: `dashboard/src/test/setup.ts`

Add Vitest/Testing Library and Playwright before feature UI.

### Task 13.2: Add Strategy routes and typed API client

**Files:**
- Create: `dashboard/src/app/strategies/page.tsx`
- Create: `dashboard/src/app/strategies/new/page.tsx`
- Create: `dashboard/src/app/strategies/[slug]/page.tsx`
- Create: `dashboard/src/app/strategies/[slug]/source/page.tsx`
- Create: `dashboard/src/app/strategies/[slug]/backtests/page.tsx`
- Create: `dashboard/src/app/strategies/[slug]/proposals/page.tsx`
- Create: `dashboard/src/app/paper/page.tsx`
- Create: `dashboard/src/app/admin/strategy-reviews/page.tsx`
- Modify: `dashboard/src/lib/api.ts`
- Modify: `dashboard/src/types/index.ts`
- Modify: `dashboard/src/components/layout/sidebar.tsx`

### Task 13.3: Build chat-only Strategy Builder

**Files:**
- Create: `dashboard/src/components/strategies/builder-chat.tsx`
- Create: `dashboard/src/components/strategies/builder-message.tsx`
- Create: `dashboard/src/components/strategies/job-status.tsx`
- Test: `dashboard/src/components/strategies/builder-chat.test.tsx`
- E2E: `dashboard/e2e/strategy-builder.spec.ts`

**UX:** No permanent form/spec side panel. AI asks concise questions; final summary appears in chat; user confirms generation; validation/backtest/change actions appear as messages/buttons. Source/diff is a separate page/modal.

### Task 13.4: Build Marketplace, version, source, and collaboration screens

Show immutable versions, license/download, provenance, source, diff, tests, dependency/SBOM, benchmark/forward metrics, issues/forks/proposals/contributors, review badges, and update notifications. Clearly distinguish manually reviewed initial version from auto-validated later versions.

### Task 13.5: Build Paper account and risk screens

Show $500 account, season history, allocations, unallocated cash, positions/orders/deals/equity, rejected-signal reasons, feed health, user risk settings, activation version pin, reset flow, and kill/stop controls.

---

## Milestone 14 — Security, moderation, and operational controls

### Task 14.1: Add audit coverage for all sensitive actions

Audit signup, role/status changes, strategy generation, package requests, sandbox builds/runs, reviews, publication, activation, risk changes, resets, kill actions, downloads, and admin suspension. Logs must redact tokens, code secrets, SMTP credentials, broker credentials, and raw auth headers.

### Task 14.2: Add content/security moderation

Automated checks cover forbidden claims, malicious code patterns, dependency risks, license mismatch, plagiarism flags, runtime capabilities, look-ahead behavior, deterministic tests, resource abuse, and unsafe files. Admin review supports approve/request-changes/reject/suspend with mandatory reason.

### Task 14.3: Add abuse and queue controls

Public signup requires verification and captcha. Codex remains global FIFO but users have bounded active/queued jobs. Backtest/build concurrency is globally bounded. Rate-limit auth, generation, proposal, download, and benchmark submission endpoints.

---

## Milestone 15 — Tests, migrations, and cutover rehearsal

### Task 15.1: Run complete local quality gates

**Commands:**
- `cd api && uv sync && uv run ruff check . && uv run pyright && uv run pytest -q`
- `cd bot && uv sync && uv run pytest -q`
- `cd dashboard && bun install --frozen-lockfile && bun run lint && bun run test && bun run build`
- `cd dashboard && bunx playwright test`
- `cd sandbox-manager && go test ./...`
- `cd strategy-builder && bun test && bun run build`
- `cd strategy-sdk && uv run pytest -q`

Expected: all pass with no skipped security-critical tests.

### Task 15.2: Rehearse data/auth migration

Restore a production-data copy into an isolated environment, run dry-run and real migration, reconcile object counts/checksums, verify owner/user/account mappings, and verify rollback to legacy auth/data without loss.

### Task 15.3: Run end-to-end acceptance suite

1. Public user signs up, verifies email, and receives role trader + $500 account.
2. User describes a multi-symbol/multi-timeframe strategy in chat.
3. Codex asks clarifications and generates code/tests/spec.
4. A requested PyPI dependency is built/scanned in gVisor; malicious requests fail safely.
5. Development, validation, and sealed backtests are deterministic.
6. Initial public publish waits for admin; approval creates downloadable open-source version and official track.
7. Another user forks/proposes a natural-language change; accepted proposal creates a new candidate/version.
8. Existing activation remains pinned after update.
9. Paper activation obeys risk/allocation/order/position rules.
10. No MT5 order is emitted by any R1 path.
11. Codex quota blocks before exceeding policy and preserves drafts.
12. Feed staleness pauses new entries visibly.

---

## Milestone 16 — Dokploy deployment and production verification

### Task 16.1: Provision production services

Create/attach PostgreSQL, Stalwart, market-data worker, paper worker, Strategy Builder, sandbox manager host service, persistent Parquet/artifact volumes, and backup schedules. Existing API/dashboard/MT5 services remain independently deployable.

### Task 16.2: Deploy dark

Deploy database migrations and services with all user-facing feature flags off. Verify old production behavior first. Enable owner-only Strategy Lab, then Paper live, then publication, then open signup only after all gates pass.

### Task 16.3: Verify production endpoints and workers

Check health/readiness for API, dashboard, PostgreSQL, Stalwart queue, market-data freshness, Codex quota, sandbox manager/runsc, backtest queue, paper queue, and official-track scheduler. Alert on stale feed, queue growth, sandbox failures, disk, DB, SMTP bounces, and Codex quota exhaustion.

### Task 16.4: Verify UI with screenshots at all required breakpoints

Capture and inspect every changed page at:
- Mobile: 390x844
- Tablet: 768x1024
- Desktop: 1440x900
- Wide: 1920x1080

Pages: sign-in/up/verify/reset, strategies list, chat builder, strategy overview/source/backtest/proposals, paper account, risk settings, admin review, and failure/empty/loading states. Do not report UI completion without screenshot evidence.

### Task 16.5: Production canary and rollback drill

Use owner plus one test trader. Create a harmless deterministic strategy, run official backtest/paper, publish/activate/propose/update, test email and quota, then execute rollback of each deployable service without deleting new data. Keep Open signup off until canary and rollback pass.

---

# Files likely to change

## Existing
- `Dockerfile`
- `api/pyproject.toml`, `api/uv.lock`, `api/.env.example`
- `api/src/main.py`, `api/src/config.py`, `api/src/security.py`, `api/src/dependencies.py`
- `api/src/access_store.py`, `api/src/account_store.py`, `api/src/platform_store.py`
- `api/src/routers/auth.py`, `api/src/routers/access.py`, `api/src/routers/platform.py`
- `api/tests/test_platform_store.py`, `api/tests/test_platform_api.py`
- `dashboard/package.json`, `dashboard/bun.lock`
- `dashboard/src/proxy.ts`, `dashboard/src/app/layout.tsx`
- `dashboard/src/app/api/[...path]/route.ts`
- `dashboard/src/lib/api.ts`, `dashboard/src/types/index.ts`
- `dashboard/src/components/layout/sidebar.tsx`
- existing Clerk sign-in/sign-up files

## New top-level components
- `strategy-sdk/`
- `strategy-builder/`
- `sandbox-manager/`
- `sandbox-images/`
- `infra/local/`, `infra/stalwart/`, `infra/gvisor/`
- `api/alembic/`
- new API domains under `api/src/{auth,db,models,repositories,services,market_data,backtest,execution,sandbox,workers}/`
- new strategy/paper/admin pages and components under `dashboard/src/`

---

# Primary risks and mitigations

| Risk | Mitigation |
|---|---|
| Public arbitrary code escapes container | gVisor, tiny host manager, no socket/API exposure, no network/secrets/mounts, adversarial tests |
| Malicious PyPI package | isolated build, exact hashes, SBOM/license/OSV scans, disposable runtime, package may be rejected |
| Shared Codex subscription abuse/terms | global queue, 10-point guard, feature flag, verified users, terms gate |
| Free market-data SLA/license | versioned provider interface, Dukascopy labeling, MT5 validation, stale pause, no raw redistribution, public-license gate |
| Self-hosted mail deliverability | PTR/A/SPF/DKIM/DMARC, direct port test, canary deliveries, low volume, open-signup gate |
| Scope/complexity | strict Release 1 non-goals, independent milestones, feature flags, canary rollout |
| Migration breaks existing trading app | idempotent dry-run migration, dual-read/cutover window, backups, old-path regression suite |
| Backtest overfitting/misleading results | chronological validation, sealed run, immutable audit, standard risk/cost model, ambiguity/data-quality metrics |
| Strategy update changes live behavior | immutable versions, explicit user upgrades, per-version tracks |

---

# Release 1 definition of done

Release 1 is done only when all of the following are true:

- [ ] Clerk is removed and Better Auth is the only auth source.
- [ ] Open signup is verified-email/captcha protected and creates a trader + $500 paper account.
- [ ] Stalwart mail identity and deliverability checks pass.
- [ ] Existing users/accounts/platform data are migrated to PostgreSQL without loss.
- [ ] Dukascopy M1 Bid/Ask data for all six symbols is versioned, quality-checked, and aggregated.
- [ ] Chat-only Builder creates deterministic multi-symbol/multi-timeframe Python strategy artifacts.
- [ ] Codex usage cannot exceed the configured Platform weekly share under tested conditions.
- [ ] Arbitrary dependency builds/runs are isolated by gVisor and pass adversarial tests.
- [ ] Backtests include development, validation, sealed benchmark, costs, ambiguity, and data-quality disclosures.
- [ ] Every user can allocate and run strategies on a $500 paper account under user-owned risk policy.
- [ ] Public source, downloads, licenses, immutable versions, forks/issues/proposals, reviews, and provenance work.
- [ ] First public version requires Admin; later compatible versions pass automated gates; activations never auto-upgrade.
- [ ] No R1 code path can send a real MT5 order.
- [ ] All unit/integration/E2E/security/build checks pass.
- [ ] Every changed UI route is screenshot-verified on mobile/tablet/desktop/wide.
- [ ] Dokploy production canary, backups, monitoring, and rollback drill pass.
