# Design QA — Beginner-First Copy Trading Marketplace

## Source and build

- Selected direction: Option 2, Trader Discovery Focus.
- Reference: `/Users/parsaz/.codex/generated_images/019f7454-8bb0-7d92-9641-707b8c8d5f46/exec-ef6cc54c-510e-447c-b8d9-9db4b10ff1d7.png`
- Local preview: `http://localhost:3000/copy-trading?preview=1`
- Desktop capture: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/13-desktop-responsive-final.png`
- Mobile capture: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/16-mobile-final-clean.png`
- Final comparison: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/17-side-by-side-final.png`
- Dropdown annotation source truth: User Comment 1 plus the pre-change desktop capture above.
- Customized dropdown, closed: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/21-custom-select-closed-full.png`
- Customized dropdown, open: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/20-custom-select-open-full.png`
- Customized dropdown, mobile: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/19-custom-select-mobile.png`
- Dropdown full-view comparison: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/22-select-full-comparison.png`
- Dropdown focused comparison: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/23-select-focused-comparison.png`

## Viewports and states

- Desktop QA: browser-capped 1280 × 720 viewport with a full-page capture at the default Copy traders state and Harbor Strategy selected.
- Mobile QA: 390 × 844 viewport with the directory, filters, first trader card, and persistent bottom navigation visible.
- Preview data is gated by `NEXT_PUBLIC_COPY_TRADING_PREVIEW=true` plus `?preview=1`; the production build keeps this off.

## Interaction verification

- Search filters traders by name and returns to the neutral directory when cleared.
- Copy traders and Share my trades tabs update the URL and content.
- Start copying opens the accessible guided dialog.
- Account, Balanced risk, money-loss review, and Start paper copying complete in order.
- Dialog closes after activation and restores the directory state.
- Mobile navigation and the main trader-selection controls remain keyboard-addressable.
- Customized dropdowns support Arrow keys, Home/End, Enter/Space selection, Escape dismissal, outside-click dismissal, focus restoration, and visible selected state.
- Dropdown menus render above scroll containers and reposition against available viewport space.
- Source inspection confirms there are no remaining native `<select>` elements in the dashboard application.
- Browser console contained only React development and Fast Refresh informational messages; no application errors were observed.

## Comparison and fixes

| Pass | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| 1 | P1 | Primary Start copying action was clipped below the desktop viewport. | Reduced vertical density and kept the action inside the trader detail card. |
| 2 | P1 | The desktop layout collapsed too early near 1280px and pushed trader details below the directory. | Gave the sidebar a measured 1180px expansion breakpoint and enabled the two-column directory at the large breakpoint. |
| 2 | P1 | Mobile inherited the desktop sidebar and compressed trader statistics. | Replaced it with a five-item bottom navigation and stacked card metrics below trader identity. |
| 3 | P2 | The selected concept still showed obsolete Platform, Risk, Bot, and Analysis navigation. | Removed those entries intentionally per the approved product plan; redirects preserve old URLs. |
| 3 | P2 | The implementation uses slightly tighter spacing than the concept. | Retained the tighter spacing so the complete primary decision is visible at the supported desktop viewport without reducing legibility. |
| 4 | P1 | Native browser dropdown menus broke the product's visual language and varied by operating system/browser. | Replaced every dashboard select with the shared branded combobox/listbox component, including Copy filters, MT5 setup, Orders, and Access roles. |
| 4 | P2 | An absolutely positioned custom menu could be clipped inside horizontally scrollable tables. | Moved the listbox to a viewport-positioned portal that measures available space and opens above or below the trigger. |
| 4 | P2 | Escape initially dismissed the menu only while an option held focus. | Added Escape handling to both the trigger and listbox, then verified focus restoration and zero open listboxes. |

## Accessibility and implementation checks

- Tabs expose tablist/tab/tabpanel roles and keyboard navigation.
- The setup dialog traps focus, closes on Escape, restores focus, and exposes an error summary/status announcements.
- Buttons and inputs have visible focus styles and labels.
- Combobox triggers expose expanded, controls, required, invalid, and listbox relationships; options expose selected state.
- Desktop and mobile layouts avoid clipped controls and horizontal overflow in the tested states.

## Required fidelity surfaces — dropdown iteration

- Fonts and typography: menu labels use the existing dashboard font, 14px UI sizing, and the same primary/secondary text weights as adjacent filters.
- Spacing and layout rhythm: 40px compact triggers, 8px menu offset, 12px radii, and 10px option padding preserve the existing control rhythm.
- Colors and visual tokens: triggers and menus use `bg-bg-tertiary`, `bg-bg-elevated`, border, accent, and text tokens already used by the dashboard.
- Image and icon fidelity: existing Lucide filter icons are retained; ChevronDown and Check use the same icon family with no placeholder or handmade assets.
- Copy and content: default labels remain Markets, Trading history, and Largest drop; active filters show the chosen value without changing surrounding copy.

## Compact command rail iteration

- Selected sidebar reference: `/Users/parsaz/.codex/generated_images/019f7454-8bb0-7d92-9641-707b8c8d5f46/exec-e3e54132-bf38-4ede-92b0-36523aca4f30.png`
- Final desktop capture: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/29-sidebar-option2-polished-desktop.png`
- Portfolio flyout capture: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/25-sidebar-option2-portfolio-menu.png`
- Mobile capture: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/26-sidebar-option2-mobile.png`
- Final visual comparison: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/30-sidebar-option2-final-comparison.png`

### Fidelity and interaction verification

- Replaced the eight-row desktop menu with the selected four-destination command rail: Home, Copy, Portfolio, and Account.
- Matched the reference with a 112px dark rail, centered icon-label destinations, a compact blue-violet selected surface, a dashed lower divider, connection status, account avatar, and account label.
- Preserved every existing destination through accessible Portfolio and Account flyouts rather than removing routes.
- Portfolio exposes Open positions, New order, and Trade history; Account exposes Account setup, Access, and Settings.
- Group triggers expose `aria-expanded` and `aria-haspopup`; the flyouts expose `menu`/`menuitem` roles, dismiss on outside click or Escape, and restore focus after Escape.
- The active state covers child routes, so the rail keeps users oriented while visiting Positions, Orders, History, Account setup, Access, or Settings.
- The existing five-item mobile bottom navigation is preserved at 390 × 844; the desktop rail is hidden at that breakpoint.
- Browser verification found four desktop primary destinations, three routes in each grouped flyout, zero application console errors, and no clipped rail controls at 1280 × 720.

### Comparison fixes

| Pass | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| 1 | P1 | The old sidebar exposed eight equally weighted destinations and consumed 220px at common desktop widths. | Replaced it with the selected 112px command rail and four beginner-friendly destinations. |
| 1 | P1 | Collapsing the navigation risked making Orders, History, Access, and Settings unreachable. | Added labeled, keyboard-accessible Portfolio and Account flyouts that retain every route. |
| 2 | P2 | The first active state was darker and rounder than the selected concept. | Tightened the corner radius to 12px and added the reference-like blue-violet gradient and soft elevation. |
| 2 | P2 | The lower connection and account area did not match the reference hierarchy. | Added the green status dot, LS preview avatar, account label, and downward disclosure cue. |

### Required fidelity surfaces — command rail

- Typography: short 10–11px rail labels and compact status copy preserve the selected reference hierarchy without introducing a new font.
- Spacing: 76 × 82px primary targets, 16px vertical rhythm, and the 112px rail reproduce the concept while preserving comfortable hit areas.
- Colors and elevation: the selected item uses a restrained blue-violet gradient, accent border, and cool shadow over the existing dark token system.
- Icons: the product's existing Lucide icon family supplies the same outlined visual language as the reference; no placeholder or raster icons were introduced.
- Content: technical destinations are grouped behind plain labels, while specific route names remain visible in flyouts with beginner-oriented descriptions.

## Collapsible command rail iteration

- Source visual truth: `/Users/parsaz/.codex/generated_images/019f7454-8bb0-7d92-9641-707b8c8d5f46/exec-e3e54132-bf38-4ede-92b0-36523aca4f30.png`, plus the user-requested standard collapse/expand behavior.
- Expanded implementation: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/32-sidebar-expanded-settled.png`
- Collapsed implementation: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/33-sidebar-collapsed.png`
- Collapsed flyout implementation: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/34-sidebar-collapsed-flyout.png`
- Full-view comparison: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/35-sidebar-collapse-full-comparison.png`
- Focused rail comparison: `/Users/parsaz/.codex/visualizations/2026/07/18/019f7454-8bb0-7d92-9641-707b8c8d5f46/copy-trading-implementation/36-sidebar-collapse-focused-comparison.png`
- Viewport and state: 1280 × 720 desktop viewport, Copy selected, expanded rail, collapsed rail, and collapsed Portfolio flyout.

### Findings and comparison history

| Pass | Severity | Finding | Resolution and post-fix evidence |
| --- | --- | --- | --- |
| 1 | P1 | The selected rail had no way to reclaim horizontal space or restore its labeled state. | Added a persistent 112px expanded state and 72px icon state with an edge-mounted trigger; both states are visible in the focused comparison. |
| 1 | P1 | The expected `Command+B` / `Control+B` interaction was absent. | Added both shortcuts, prevented the browser default, closed open flyouts during the transition, and verified both directions in the browser. |
| 1 | P2 | An icon-only state could make destinations difficult for beginners to identify. | Preserved accessible names and added branded hover/focus hints for Home, Copy, Portfolio, and Account. |
| 2 | P2 | Grouped destinations still needed to remain usable after collapsing. | Repositioned flyouts against the 72px rail and verified all three Portfolio menu items remain visible and interactive. |

### Final verification

- The edge trigger exposes `aria-label`, `aria-expanded`, `aria-controls`, and `aria-keyshortcuts="Meta+B Control+B"`.
- `Control+B` expands, `Command+B` collapses, and the selected state persists after reload.
- The transition closes any open grouped menu to avoid a detached flyout.
- The expanded state preserves the selected Option 2 proportions, typography, colors, icon family, account status, and navigation copy.
- The collapsed state keeps the same assets and tokens; only labels and secondary account copy are visually condensed.
- Browser verification found four collapsed hover/focus hints, one unambiguous toggle control, three Portfolio flyout items, and zero application console errors.
- No P0, P1, or P2 findings remain. The Next.js development indicator overlaps the local-only account avatar in captures; it is not part of the application or production build.

## Collapsed flyout overlay correction

- Source visual truth: `/var/folders/6f/_j2cbcxx323gkcrcb10_cqg40000gn/T/codex-clipboard-01695ee4-ce35-4881-b942-658ae8e2aba8.png`
- Browser-rendered implementation: `/tmp/trading-signal-copier-sidebar-overlay-fixed.png`
- Viewport: 1311 × 994 desktop.
- State: collapsed command rail, Copy selected, Portfolio flyout open, API error state visible behind the flyout.
- Full-view and focused evidence: the source and corrected implementation were opened together at the same viewport and interaction state; the flyout region was also measured in-browser before and after the correction.

### Findings and comparison history

| Pass | Severity | Finding | Resolution and post-fix evidence |
| --- | --- | --- | --- |
| 1 | P1 | The flyout was vertically centered against its trigger, placing it at y=157.75 and obscuring the page title, view tabs, progress stepper, and search controls. | Anchored the flyout to the trigger's top edge at y=250, keeping the page title and primary view switch unobstructed. |
| 1 | P1 | The 95%-opaque glass surface allowed unrelated page copy and controls to remain visibly layered through the menu. | Replaced the translucent surface with the opaque elevated background token and strengthened its elevation/ring, producing a visually self-contained navigation surface. |
| 1 | P2 | The sidebar had no explicit stacking level while the header used z=30, making grouped navigation dependent on incidental stacking-context behavior. | Established the sidebar at z=40 and the flyout at z=60; measured browser styles confirm the intended order. |

### Interaction and fidelity verification

- Escape dismissal was exercised and left zero open Portfolio menus.
- Reopening produced one menu, and clicking the main surface dismissed it again.
- The flyout remains keyboard-addressable and retains `menu`/`menuitem` semantics.
- Fonts and typography retain the existing 10px group label, 14px route labels, and 11px descriptions.
- Spacing and layout retain the 270px menu width and 48px rail trigger while removing the destructive vertical translation.
- Colors use the existing opaque `bg-bg-secondary`, border, text, and accent tokens; no new palette or gradient was introduced.
- Icon and image fidelity is unchanged: the existing Lucide route icons remain sharp and consistently sized.
- Copy and content remain unchanged; only positioning, opacity, clipping protection, and stacking were corrected.
- Browser console inspection showed no application errors caused by the flyout correction.
- No actionable P0, P1, or P2 overlay findings remain.

## Result

final result: passed
