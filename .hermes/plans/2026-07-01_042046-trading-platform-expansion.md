# Trading Platform Expansion Implementation Plan

> **For Hermes:** Implement this plan incrementally with strict TDD for backend behavior and browser verification for dashboard flows.

**Goal:** Convert the existing Telegram → LLM → MT5 signal copier into a broader multi-user trading automation platform with copy-trading, manual trade intents, paper execution, provider subscriptions, and per-user risk controls.

**Architecture:** Preserve the existing MT5 bot/dashboard as one capability, but route all new trading actions through a unified `TradeEvent` layer. Every source — Telegram parser, manual dashboard orders, webhooks, and provider/copier events — creates normalized trade events. User-specific risk policies decide whether and how each event becomes a paper execution now, and a live MT5 execution later.

**Tech Stack:** FastAPI + JSON-backed local stores for MVP, Next.js dashboard, existing Clerk/local auth, existing account ownership model, paper/simulated execution only for this phase.

---

## Phase 0 — Guardrails

- Do not deploy, redeploy, stop, or mutate Dokploy production unless explicitly requested later.
- All execution in this phase is paper/simulated; no live broker orders.
- Keep existing `/api/orders` MT5 behavior intact.
- Add new platform APIs under `/api/platform/*`.
- Add dashboard feature pages without breaking existing MT5 dashboard pages.

---

## Phase 1 — Backend MVP Domain

### Task 1: Platform store and domain objects

**Objective:** Add JSON-backed storage for providers, subscriptions, risk policies, trade events, and executions.

**Files:**
- Create: `api/src/platform_store.py`
- Create tests: `api/tests/test_platform_store.py`

**Core behavior:**
- `create_provider(owner_user_id, name, source_type, description)`
- `list_providers(user_id)` returns public providers and owned providers.
- `upsert_risk_policy(user_id, payload)` stores defaults: paper mode, fixed lot, require SL, allowed symbols, max daily loss.
- `create_subscription(follower_user_id, provider_id, copy_mode, multiplier, fixed_lot, paper)`
- `create_trade_event(provider_id, action, symbol, side, entry, stop_loss, take_profits, source)`
- `process_trade_event(event_id)` creates per-follower paper executions after risk checks.

### Task 2: Risk engine

**Objective:** Make copy decisions deterministic and safe.

**Files:**
- Add risk helpers inside `api/src/platform_store.py` or separate `api/src/platform_risk.py` if the store grows too large.
- Test in `api/tests/test_platform_store.py`.

**Required rules:**
- Reject events without SL when `require_stop_loss=true`.
- Reject symbols outside `allowed_symbols`.
- Reject if daily realized paper PnL would breach `max_daily_loss`.
- Support `fixed_lot`, `multiplier`, and `paper` copy settings.

### Task 3: Platform API routes

**Objective:** Expose backend domain to the dashboard.

**Files:**
- Create: `api/src/routers/platform.py`
- Modify: `api/src/main.py`
- Create tests: `api/tests/test_platform_api.py`

**Endpoints:**
- `GET /api/platform/overview`
- `GET/POST /api/platform/providers`
- `GET/PUT /api/platform/risk-policy`
- `GET/POST /api/platform/subscriptions`
- `GET/POST /api/platform/trade-events`
- `POST /api/platform/trade-events/{event_id}/process`
- `GET /api/platform/executions`
- `POST /api/platform/stress-test`

### Task 4: Webhook/manual event path

**Objective:** Let dashboards or external strategies submit normalized trade events.

**Files:**
- Extend: `api/src/routers/platform.py`
- Test in: `api/tests/test_platform_api.py`

**Required behavior:**
- Manual events can be created by the authenticated user.
- Owner-created provider events fan out to subscribers in paper mode.
- Stress endpoint generates many events and verifies idempotent processing.

---

## Phase 2 — Dashboard MVP

### Task 5: API client types and calls

**Files:**
- Modify: `dashboard/src/lib/api.ts`
- Modify: `dashboard/src/types/index.ts`

**Add calls:**
- `getPlatformOverview`
- `getProviders`, `createProvider`
- `getRiskPolicy`, `saveRiskPolicy`
- `getSubscriptions`, `createSubscription`
- `createTradeEvent`, `processTradeEvent`
- `getExecutions`
- `runPlatformStressTest`

### Task 6: Navigation and Platform pages

**Files:**
- Modify: `dashboard/src/components/layout/sidebar.tsx`
- Create: `dashboard/src/app/platform/page.tsx`
- Create: `dashboard/src/app/copy-trading/page.tsx`
- Create: `dashboard/src/app/risk/page.tsx`

**UI:**
- Platform overview cards: providers, followers, paper executions, blocked risk checks.
- Provider creation form.
- Copy subscription form.
- Risk policy editor.
- Manual trade event form.
- Stress-test button with visible result table.

---

## Phase 3 — Verification

### Backend commands

```bash
cd api
uv run pytest tests/test_platform_store.py tests/test_platform_api.py -q
uv run pytest tests -q
uv run ruff check src tests
```

### Frontend commands

```bash
cd dashboard
npm run lint
npm run build
```

### Local browser stress verification

1. Start API locally on port `8000` with isolated data dir.
2. Start dashboard locally on port `3000` with API URL pointed to local API.
3. Use browser to:
   - Create/login local admin if Clerk is disabled locally.
   - Open `/platform` and confirm overview loads.
   - Create provider.
   - Add risk policy.
   - Add subscription.
   - Create manual trade event.
   - Process event and verify paper execution appears.
   - Run stress test and confirm UI reports success.
4. Check browser console for JS errors.

---

## Phase 4 — Later, after MVP works

- Telegram listener emits `TradeEvent` instead of directly executing MT5.
- Provider MT5 account mirroring: poll provider positions and emit open/modify/close events.
- Demo MT5 executor adapter consumes accepted executions.
- Marketplace profiles, Trust Score, channel intelligence/backtesting, payments.
- Live-money controls: signed confirmations, account-level kill switch, audit exports, SOC-grade secrets.

---

## Acceptance Criteria for This Session

- Backend platform domain is implemented and tested.
- Dashboard has usable MVP pages for platform/copy/risk operations.
- All new behavior is paper/simulated.
- Browser verification can exercise the full flow locally without production changes.
- Existing MT5 dashboard behavior is not intentionally changed.
