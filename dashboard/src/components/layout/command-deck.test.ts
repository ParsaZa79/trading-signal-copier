import { describe, expect, it } from "vitest";

import type { Position } from "@/types";
import {
  formatRecentAge,
  rememberRecentDestination,
  searchCommandCatalog,
} from "./command-deck";

const position: Position = {
  ticket: 8137402,
  symbol: "XAUUSD",
  type: "buy",
  volume: 0.5,
  price_open: 2400,
  price_current: 2410,
  sl: 2390,
  tp: 2430,
  profit: 5,
  swap: 0,
  time: null,
};

describe("command deck search", () => {
  it("finds pages and quick actions", () => {
    expect(searchCommandCatalog("trade history", [])).toEqual(
      expect.arrayContaining([expect.objectContaining({ id: "page-history" })])
    );
    expect(searchCommandCatalog("safety limits", [])).toEqual(
      expect.arrayContaining([expect.objectContaining({ id: "action-review-limits" })])
    );
  });

  it("finds markets and live position tickets", () => {
    expect(searchCommandCatalog("XAU/USD", [position])).toEqual(
      expect.arrayContaining([expect.objectContaining({ id: "market-XAUUSD" })])
    );
    expect(searchCommandCatalog("8137402", [position])).toEqual([
      expect.objectContaining({ id: "ticket-8137402", href: "/positions?ticket=8137402" }),
    ]);
  });
});

describe("recent destinations", () => {
  it("deduplicates, orders, and caps recent pages", () => {
    const recent = [
      { href: "/positions", visitedAt: 1 },
      { href: "/history", visitedAt: 2 },
      { href: "/settings", visitedAt: 3 },
    ];

    expect(rememberRecentDestination(recent, "/history", 4)).toEqual([
      { href: "/history", visitedAt: 4 },
      { href: "/positions", visitedAt: 1 },
      { href: "/settings", visitedAt: 3 },
    ]);

    expect(rememberRecentDestination(recent, "/", 5)).toEqual([
      { href: "/", visitedAt: 5 },
      { href: "/positions", visitedAt: 1 },
      { href: "/history", visitedAt: 2 },
    ]);
  });

  it("formats useful relative times", () => {
    const now = Date.UTC(2026, 6, 22, 12);
    expect(formatRecentAge(now - 30_000, now)).toBe("Just now");
    expect(formatRecentAge(now - 12 * 60_000, now)).toBe("12 min ago");
    expect(formatRecentAge(now - 30 * 60 * 60_000, now)).toBe("Yesterday");
  });
});
