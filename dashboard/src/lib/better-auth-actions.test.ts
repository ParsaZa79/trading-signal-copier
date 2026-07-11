import { describe, expect, it, vi } from "vitest";
import { authCaptchaHeaders, safeAuthCallback, signInWithPassword, requestPasswordReset, resetPassword, signupAvailability } from "./better-auth-actions";

describe("Better Auth form actions", () => {
  it("sends the Turnstile token in the required header", () => {
    expect(authCaptchaHeaders("captcha-token")).toEqual({ "x-captcha-response": "captcha-token" });
  });

  it("returns a generic error for invalid credentials", async () => {
    const email = vi.fn().mockResolvedValue({ data: null, error: { code: "INVALID_EMAIL_OR_PASSWORD" } });
    await expect(signInWithPassword({ signIn: { email } }, "user@example.test", "wrong", "captcha")).resolves.toEqual({ ok: false, message: "Unable to sign in. Check your details and try again." });
  });

  it("handles unverified email without exposing account details", async () => {
    const email = vi.fn().mockResolvedValue({ data: null, error: { code: "EMAIL_NOT_VERIFIED" } });
    await expect(signInWithPassword({ signIn: { email } }, "user@example.test", "password", "captcha")).resolves.toEqual({ ok: false, emailVerificationRequired: true, message: "Verify your email before signing in." });
  });

  it("always gives a generic password reset response and sends Turnstile", async () => {
    const requestPasswordResetCall = vi.fn().mockResolvedValue({ data: null, error: { code: "USER_NOT_FOUND" } });
    await expect(requestPasswordReset({ requestPasswordReset: requestPasswordResetCall }, "missing@example.test", "/sign-in/reset-password", "captcha-token")).resolves.toEqual({ ok: true, message: "If an account exists, a reset link has been sent." });
    expect(requestPasswordResetCall).toHaveBeenCalledWith(
      { email: "missing@example.test", redirectTo: "/sign-in/reset-password" },
      { headers: { "x-captcha-response": "captcha-token" } },
    );
  });

  it("submits a new password with its reset token", async () => {
    const resetPasswordCall = vi.fn().mockResolvedValue({ data: {}, error: null });
    await expect(resetPassword({ resetPassword: resetPasswordCall }, "token", "replacement-password")).resolves.toEqual({ ok: true });
    expect(resetPasswordCall).toHaveBeenCalledWith({ token: "token", newPassword: "replacement-password" });
  });

  it("allows only local post-login callback paths", () => {
    expect(safeAuthCallback("/positions?symbol=XAUUSD")).toBe("/positions?symbol=XAUUSD");
    expect(safeAuthCallback("https://evil.example/phish")).toBe("/");
    expect(safeAuthCallback("//evil.example/phish")).toBe("/");
    expect(safeAuthCallback(null)).toBe("/");
  });

  it("does not expose a usable signup form when signup is closed", () => {
    expect(signupAvailability(false)).toEqual({ showForm: false, message: "Account registration is closed" });
  });
});
