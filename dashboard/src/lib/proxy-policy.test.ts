import { describe, expect, it } from "vitest";
import { betterAuthRouteDecision, hasApiProxyIdentity, isPublicAuthRoute } from "./proxy-policy";

describe("Better Auth route protection", () => {
  it("keeps auth endpoints and sign-in public", () => {
    expect(isPublicAuthRoute("/api/auth/sign-in/email")).toBe(true);
    expect(isPublicAuthRoute("/sign-in/reset-password")).toBe(true);
  });

  it("keeps signup route reachable so closed signup can explain access", () => {
    expect(isPublicAuthRoute("/sign-up")).toBe(true);
  });

  it("redirects an unauthenticated dashboard request to sign-in with a safe callback", () => {
    expect(betterAuthRouteDecision(new URL("https://dashboard.test/positions?symbol=XAUUSD"), false)).toEqual({
      action: "redirect",
      location: "https://dashboard.test/sign-in?callbackURL=%2Fpositions%3Fsymbol%3DXAUUSD",
    });
  });

  it("allows authenticated and public requests", () => {
    expect(betterAuthRouteDecision(new URL("https://dashboard.test/positions"), true)).toEqual({ action: "next" });
    expect(betterAuthRouteDecision(new URL("https://dashboard.test/api/auth/get-session"), false)).toEqual({ action: "next" });
  });
});

describe("dashboard API proxy identity policy", () => {
  it("accepts only a non-empty Better Auth bearer token", () => {
    expect(hasApiProxyIdentity("better-auth", "Bearer signed.jwt.value", null)).toBe(true);
    expect(hasApiProxyIdentity("better-auth", null, null)).toBe(false);
    expect(hasApiProxyIdentity("better-auth", "Bearer ", null)).toBe(false);
    expect(hasApiProxyIdentity("better-auth", "Basic abc", null)).toBe(false);
  });

  it("preserves Clerk identity headers only in rollback mode", () => {
    expect(hasApiProxyIdentity("clerk", null, "user_clerk")).toBe(true);
    expect(hasApiProxyIdentity("clerk", "Bearer ignored", null)).toBe(false);
    expect(hasApiProxyIdentity("local", "Bearer stale", "user_clerk")).toBe(false);
  });
});
