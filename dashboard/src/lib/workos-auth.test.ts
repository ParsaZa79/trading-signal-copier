import { describe, expect, it } from "vitest";
import {
  authErrorMessage,
  isValidEmail,
  normalizeEmail,
  safeReturnTo,
  workosRedirectUri,
} from "./workos-auth";

describe("WorkOS auth helpers", () => {
  it("normalizes and validates email addresses", () => {
    expect(normalizeEmail("  Owner@Example.COM ")).toBe("owner@example.com");
    expect(isValidEmail("owner@example.com")).toBe(true);
    expect(isValidEmail("not-an-email")).toBe(false);
  });

  it("only accepts same-origin return paths", () => {
    expect(safeReturnTo("/positions?ticket=42")).toBe("/positions?ticket=42");
    expect(safeReturnTo("https://attacker.example")).toBe("/");
    expect(safeReturnTo("//attacker.example")).toBe("/");
    expect(safeReturnTo("/\\attacker.example")).toBe("/");
  });

  it("normalizes the configured public callback URI", () => {
    expect(
      workosRedirectUri("  https://dashboard.example.com/auth/callback  "),
    ).toBe("https://dashboard.example.com/auth/callback");
    expect(() => workosRedirectUri("file:///tmp/callback")).toThrow(
      "WorkOS redirect URI must use HTTP or HTTPS",
    );
  });

  it("does not expose unexpected provider errors", () => {
    expect(authErrorMessage(new Error("database shard details"), "Unable to sign in.")).toBe(
      "Unable to sign in.",
    );
    expect(authErrorMessage(new Error("Invalid email or password"), "Unable to sign in.")).toBe(
      "Invalid email or password.",
    );
  });
});
