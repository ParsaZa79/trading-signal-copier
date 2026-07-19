# Account Setup Design QA

## Evidence

- Source visual truth: `/Users/parsaz/.codex/generated_images/019f7454-8bb0-7d92-9641-707b8c8d5f46/exec-014558b7-3b90-47e7-9232-a808e7ff476e.png`
- Final desktop implementation: `/tmp/account-setup-broker-gallery-1440x1024-final.png`
- Final mobile implementation: `/tmp/account-setup-broker-gallery-mobile-390x844-final.png`
- Full-view comparison: `/tmp/account-setup-design-qa-final-comparison.png`
- Focused broker/logo comparison: `/tmp/account-setup-design-qa-focused-logos.png`
- Desktop viewport: 1440 × 1024
- Mobile viewport: 390 × 844
- Theme: dark
- State: Account Setup step 1, AMarkets selected, all 24 supported broker brands searchable

## Findings

No actionable P0, P1, or P2 findings remain.

## Full-view comparison

The verified implementation preserves the selected visual's central structure: compact navigation and top bar, four-step desktop progress path, focused broker heading, reassurance message, search field, two-row broker gallery, manual fallback, selected-broker summary, and quiet footer actions. The content width, card proportions, primary action placement, and dark visual hierarchy align closely with the source.

## Focused comparison

The focused board compares the broker gallery and its image assets at a readable scale. The implementation uses locally shipped broker marks instead of text initials or generated approximations. Each mark uses `object-contain` inside a consistent neutral image well so wide, square, light-background, and transparent source files stay recognizable without cropping or recoloring.

## Required fidelity surfaces

- Fonts and typography: Uses the product's Saans variable font, matching restrained weights, short beginner-facing copy, compact progress labels, and readable 14–16px body text. No important text is clipped.
- Spacing and layout rhythm: Desktop preserves the selected two-row card composition, deliberate blank space before the summary row, and aligned footer actions. Mobile replaces the wide progress path with a compact progress indicator and keeps actions visible above the existing bottom navigation.
- Colors and visual tokens: Existing background, border, text, accent, success, danger, and warning tokens are used throughout. Brand imagery is not recolored. No broker receives a performance or recommendation treatment.
- Image quality and asset fidelity: All 24 supported broker brands have local image files in `dashboard/public/brokers`. Higher-resolution official public assets replace low-resolution favicons for IC Markets, LiteFinance, and OANDA. Logos are rendered as images, not CSS art, text glyphs, inline SVGs, or placeholders.
- Copy and content: The screen explicitly explains that broker selection is only an account connection, not an investment choice. Technical server selection is deferred to step 2, credentials to step 3, and connection testing to step 4.

## Comparison history

### Pass 1 — blocked

- [P2] The desktop gallery exposed a clipped third row of brokers, making the implementation denser than the selected two-row visual.
  - Fix: Kept the eight source-aligned broker cards above the fold while retaining search across all 24 supported brands.
- [P2] The first mobile layout rendered the four desktop steps as a tall vertical list and pushed the primary action below the viewport.
  - Fix: Added a compact mobile “Step 1 of 4” progress treatment, a two-column broker grid, and a sticky Back/Continue action bar above the existing mobile navigation.

### Pass 2 — passed

- Post-fix desktop evidence: `/tmp/account-setup-broker-gallery-1440x1024-final.png`
- Post-fix mobile evidence: `/tmp/account-setup-broker-gallery-mobile-390x844-final.png`
- No actionable P0, P1, or P2 differences remain.

## Interactions and responsive checks

- Broker search filters the complete supported directory and found Pepperstone from a partial query.
- Selecting Pepperstone updates the selected state and advances to account type.
- Live/Demo choice filters the exact server options for the selected broker.
- Selecting `Pepperstone-MT5-Live01` advances to credentials and then the review screen.
- The preview connection action reports a successful verified state without calling production services.
- “My broker isn’t listed” advances to exact manual MT5 server entry.
- Completed progress steps can be revisited and have accessible names.
- Mobile viewport has no horizontal overflow (`scrollWidth: 384`, `innerWidth: 390`).
- The mobile action bar remains above the existing bottom navigation.
- A fresh desktop reload produced no browser console errors.
- ESLint, Vitest, TypeScript, the Next.js production build, and `git diff --check` passed.

## Follow-up polish

- [P3] The generated source image sometimes redraws supplied brand marks as wordmarks. The implementation intentionally uses the actual locally sourced image files, so a few logo proportions differ from the generated mock while remaining more accurate to the broker identity.
- [P3] The first eight brokers are presented above the fold to preserve the selected composition; the remaining supported brands are immediately available through search rather than adding a third visible row.

## Implementation checklist

- [x] Four-step guided connection flow
- [x] Searchable broker gallery
- [x] 24 local broker logo assets
- [x] Live/Demo and exact server selection
- [x] Plain-language credential and review steps
- [x] Manual server fallback
- [x] Desktop and mobile verification
- [x] Automated tests and production build

final result: passed
