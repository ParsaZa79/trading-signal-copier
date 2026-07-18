# Positions Page Design QA

## Evidence

- Selected source visual: `/Users/parsaz/.codex/generated_images/019f7454-8bb0-7d92-9641-707b8c8d5f46/exec-593a9ad7-d769-4491-bd8b-3a6e98f1c117.png`
- Final desktop implementation: `/tmp/dashboard-positions-icon-fix.png`
- Full comparison board: `/tmp/dashboard-positions-design-qa-verified-comparison.png`
- Mobile implementation: `/tmp/dashboard-positions-revised-mobile-390x844.png`
- Desktop viewport: 1440 × 1024
- Mobile viewport: 390 × 844
- Theme: dark
- State: two open trades, one trade without a stop loss, and one pending order

## Full-view comparison

The implementation preserves the selected option's beginner-first composition: a clear page title, one protection action, a three-part summary, full-width trade rows, and a quiet pending-orders disclosure. The rejected glossary panel is absent. Its former space now gives prices, results, protection status, and review actions a consistent left-to-right scan path.

## Focused comparison

No separate crop was needed because the controls and financial values remain legible in the full-size side-by-side board. The overlapping market badges were reviewed again after removing their outer circular clipping mask; both component badges now render completely.

## Required fidelity surfaces

- Typography: Uses the product's bundled font, tabular financial figures, short beginner-facing labels, and restrained secondary details.
- Spacing and layout: Summary, trade rows, and pending-orders disclosure retain the source's deliberate vertical rhythm. Desktop and mobile have no horizontal overflow.
- Color and tokens: Uses existing background, border, text, action, success, and warning tokens. Green and yellow communicate protection state without adding subjective trading judgments.
- Assets: Uses the product's existing financial market icons. Multi-part currency and commodity badges render without an outer mask, avoiding clipped circles.
- Copy: Replaces infrastructure and trading jargon with direct language such as “Result right now,” “Protected with a stop loss,” and “This trade can keep losing until you close it.”

## Comparison history

### Pass 1 — blocked

- [P2] The first implementation was vertically compressed compared with the selected visual.
  - Fix: Increased the summary, trade-row, and pending-order heights to restore the intended calm density.
- [P2] The original circular icon container clipped the overlapping parts of currency-pair badges.
  - Fix: Removed the outer mask, border, and background for position market icons while preserving the two source badges.

### Pass 2 — passed

- Post-fix evidence: `/tmp/dashboard-positions-icon-fix.png`
- No actionable P0, P1, or P2 visual or interaction issues remain.

## Interactions and responsive checks

- “Protect the unprotected trade” opens the existing trade-review dialog for the unprotected position.
- “Review trade” opens the selected position's editable protection controls.
- Dialog cancellation closes without changing the trade.
- Pending orders expand in place and expose their existing cancellation flow.
- Browser-native confirmation UI was replaced with an in-product confirmation dialog.
- The page was rendered at 390 × 844 with no horizontal overflow (`scrollWidth: 384`, `innerWidth: 390`).
- A fresh reload produced no new browser console errors.
- ESLint, Vitest, TypeScript, the Next.js production build, and `git diff --check` passed before release.

## Findings

No remaining P0, P1, or P2 findings.

## Follow-up polish

- [P3] The generated source uses illustrative market badges, while the implementation uses the product's real financial icon package for consistency across the dashboard.
- [P3] Technical lot and ticket details remain below the market name to preserve a predictable mobile scan order.
- [P3] The populated preview reports the MT5 account as connected; this is intentionally more coherent than the source mock's waiting status.

## Implementation checklist

- [x] Glossary panel removed
- [x] Full-width beginner-first trade rows
- [x] Real protection and review actions retained
- [x] Unclipped overlapping market badges
- [x] Pending-order disclosure and confirmation flow
- [x] Desktop and mobile verification
- [x] Automated checks and production build

final result: passed
