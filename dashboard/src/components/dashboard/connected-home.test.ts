import { describe, expect, it } from "vitest";
import { homeDashboardTestHelpers } from "./connected-home";

describe("home dashboard helpers", () => {
  it("creates a seven-day date window plus tomorrow for inclusive history queries", () => {
    const ranges = homeDashboardTestHelpers.dashboardRanges(new Date(2026, 6, 19, 12));

    expect(ranges).toEqual({
      todayFrom: "2026-07-19",
      todayTo: "2026-07-20",
      weekFrom: "2026-07-13",
      weekTo: "2026-07-20",
    });
  });

  it("turns a common email local-part into a friendly first name", () => {
    expect(homeDashboardTestHelpers.displayNameFromEmail("alex.smith@example.com")).toBe("Alex");
    expect(homeDashboardTestHelpers.displayNameFromEmail("samira@example.com")).toBe("Samira");
  });

  it("explains copied execution lifecycle events in plain language", () => {
    expect(homeDashboardTestHelpers.executionLabel("open", "Harbor Strategy", "EURUSD")).toBe(
      "Harbor Strategy opened EURUSD"
    );
    expect(homeDashboardTestHelpers.executionLabel("modify", "Harbor Strategy", "XAUUSD")).toBe(
      "XAUUSD protection was updated"
    );
  });
});
