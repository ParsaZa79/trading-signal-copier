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

  it("shows account data even when a daily loss policy has not been selected", () => {
    const readiness = homeDashboardTestHelpers.dashboardReadiness(
      true,
      {
        balance: 2.16,
        equity: 2.16,
        margin: 0,
        free_margin: 2.16,
        profit: 0,
      },
      null
    );

    expect(readiness).toEqual({
      accountReady: true,
      liveDataReady: true,
      riskPolicyReady: false,
    });
  });

  it("keeps the last valid account snapshot visible during a socket reconnect", () => {
    const readiness = homeDashboardTestHelpers.dashboardReadiness(
      false,
      {
        balance: 2.16,
        equity: 2.16,
        margin: 0,
        free_margin: 2.16,
        profit: 0,
      },
      1
    );

    expect(readiness).toEqual({
      accountReady: true,
      liveDataReady: false,
      riskPolicyReady: true,
    });
  });
});
