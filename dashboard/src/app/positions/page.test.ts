import { describe, expect, it } from "vitest";
import { positionsPageTestHelpers } from "./page";

describe("positions page helpers", () => {
  it("uses friendly market names for common beginner-facing symbols", () => {
    expect(positionsPageTestHelpers.friendlyMarketName("XAUUSD.a")).toBe("Gold");
    expect(positionsPageTestHelpers.friendlyMarketName("EURUSD")).toBe("Euro / US Dollar");
    expect(positionsPageTestHelpers.friendlyMarketName("US500.cash")).toBe("S&P 500");
  });

  it("formats forex and high-value market prices at useful precision", () => {
    expect(positionsPageTestHelpers.formatPrice(1.087)).toBe("1.08700");
    expect(positionsPageTestHelpers.formatPrice(2414.5)).toBe("2414.50");
    expect(positionsPageTestHelpers.formatPrice(null)).toBe("Waiting…");
  });
});
