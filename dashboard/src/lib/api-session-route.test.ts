import { describe, expect, it } from "vitest";
import { AUTH_SESSION_ENDPOINT } from "./api";

describe("WorkOS session routing", () => {
  it("uses the dashboard access endpoint", () => {
    expect(AUTH_SESSION_ENDPOINT).toBe("/api/access/me");
    expect(AUTH_SESSION_ENDPOINT.startsWith("/api/auth/")).toBe(false);
  });
});
