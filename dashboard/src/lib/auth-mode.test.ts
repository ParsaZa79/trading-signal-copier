import { describe, expect, it } from "vitest";
import { resolveAuthMode, resolvePublicAuthConfig } from "./auth-mode";

describe("public auth cutover mode", () => {
  it("uses Better Auth only for the explicit public true flag", () => {
    expect(resolveAuthMode({ NEXT_PUBLIC_BETTER_AUTH_ENABLED: "true", NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test" })).toBe("better-auth");
    expect(resolveAuthMode({ NEXT_PUBLIC_BETTER_AUTH_ENABLED: "TRUE", NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test" })).toBe("better-auth");
  });

  it("preserves Clerk rollback whenever the cutover flag is false", () => {
    expect(resolveAuthMode({ NEXT_PUBLIC_BETTER_AUTH_ENABLED: "false", NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test" })).toBe("clerk");
    expect(resolveAuthMode({ NEXT_PUBLIC_BETTER_AUTH_ENABLED: "unexpected", NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test" })).toBe("clerk");
  });

  it("does not treat the public flag as server activation", () => {
    expect(resolvePublicAuthConfig({ NEXT_PUBLIC_BETTER_AUTH_ENABLED: "true" })).toEqual({
      mode: "better-auth",
      openSignup: false,
      turnstileSiteKey: "",
    });
  });

  it("exposes only public signup and Turnstile configuration", () => {
    expect(resolvePublicAuthConfig({
      NEXT_PUBLIC_BETTER_AUTH_ENABLED: "true",
      NEXT_PUBLIC_OPEN_SIGNUP_ENABLED: "true",
      NEXT_PUBLIC_TURNSTILE_SITE_KEY: "site-key",
      TURNSTILE_SECRET_KEY: "must-not-leak",
    })).toEqual({ mode: "better-auth", openSignup: true, turnstileSiteKey: "site-key" });
  });
});
