import { describe, expect, it, vi } from "vitest";
import { getApiTokenForMode } from "./clerk-token";

describe("API token selection", () => {
  it("uses an in-memory Better Auth JWT in cutover mode", async () => {
    const betterAuth = vi.fn().mockResolvedValue("better-jwt");
    const clerk = vi.fn().mockResolvedValue("clerk-jwt");

    await expect(
      getApiTokenForMode("better-auth", { betterAuth, clerk }),
    ).resolves.toBe("better-jwt");
    expect(clerk).not.toHaveBeenCalled();
  });

  it("keeps Clerk token retrieval in rollback mode", async () => {
    const betterAuth = vi.fn().mockResolvedValue("better-jwt");
    const clerk = vi.fn().mockResolvedValue("clerk-jwt");

    await expect(getApiTokenForMode("clerk", { betterAuth, clerk })).resolves.toBe(
      "clerk-jwt",
    );
    expect(betterAuth).not.toHaveBeenCalled();
  });

  it("fails closed when the selected remote provider is unavailable", async () => {
    const fallback = vi.fn().mockResolvedValue("stale-local-token");
    await expect(getApiTokenForMode("better-auth", { fallback })).resolves.toBeNull();
    await expect(getApiTokenForMode("clerk", { fallback })).resolves.toBeNull();
    expect(fallback).not.toHaveBeenCalled();
  });

  it("uses localStorage only in explicit local mode", async () => {
    const fallback = vi.fn().mockResolvedValue("local-token");

    await expect(getApiTokenForMode("local", { fallback })).resolves.toBe(
      "local-token",
    );
  });
});
