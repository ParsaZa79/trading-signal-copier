import { describe, expect, it } from "vitest";
import { AUTH_SESSION_ENDPOINT, MT5_HEALTH_ENDPOINT } from "./api";

describe("WorkOS session routing", () => {
  it("uses the dashboard access endpoint", () => {
    expect(AUTH_SESSION_ENDPOINT).toBe("/api/access/me");
    expect(AUTH_SESSION_ENDPOINT.startsWith("/api/auth/")).toBe(false);
  });
});

describe("MT5 health routing", () => {
  it("uses the account-specific MT5 health endpoint", () => {
    expect(MT5_HEALTH_ENDPOINT).toBe("/api/health/mt5");
  });
});
