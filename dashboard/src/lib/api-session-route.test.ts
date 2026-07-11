import { describe, expect, it } from "vitest";
import { AUTH_SESSION_ENDPOINT } from "./api";

describe("remote auth session routing", () => {
  it("does not collide with Better Auth's /api/auth namespace", () => {
    expect(AUTH_SESSION_ENDPOINT).toBe("/api/access/me");
    expect(AUTH_SESSION_ENDPOINT.startsWith("/api/auth/")).toBe(false);
  });
});
