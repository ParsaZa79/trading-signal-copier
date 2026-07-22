import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  OAUTH_RETURN_TO_COOKIE,
  OAUTH_STATE_COOKIE,
  OAUTH_VERIFIER_COOKIE,
} from "@/lib/workos-auth";
import { ApiError } from "@/lib/api-error";

const mocks = vi.hoisted(() => ({
  authenticateWithCode: vi.fn(),
  cookies: vi.fn(),
  provisionDashboardAccess: vi.fn(),
  saveSession: vi.fn(),
}));

vi.mock("next/headers", () => ({ cookies: mocks.cookies }));
vi.mock("@workos-inc/authkit-nextjs", () => ({
  getWorkOS: () => ({
    userManagement: { authenticateWithCode: mocks.authenticateWithCode },
  }),
  saveSession: mocks.saveSession,
}));
vi.mock("@/lib/dashboard-access", () => ({
  dashboardNeedsSetup: (session: { active_account_id: string | null; setup_complete?: boolean }) =>
    !session.active_account_id || !session.setup_complete,
  provisionDashboardAccess: mocks.provisionDashboardAccess,
}));

import { GET } from "./route";

const publicCallback = "https://dashboard.example.com/auth/callback";

describe("WorkOS Google callback", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_WORKOS_REDIRECT_URI", publicCallback);
    vi.stubEnv("WORKOS_CLIENT_ID", "client_test");
    mocks.authenticateWithCode.mockReset();
    mocks.cookies.mockReset();
    mocks.provisionDashboardAccess.mockReset();
    mocks.provisionDashboardAccess.mockResolvedValue({
      active_account_id: "account_123",
      setup_complete: true,
    });
    mocks.saveSession.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("redirects to the public dashboard when Docker reports its internal host", async () => {
    const authResponse = {
      accessToken: "access",
      refreshToken: "refresh",
      user: { id: "user_123", email: "trader@example.com" },
    };
    const cookieValues: Record<string, string> = {
      [OAUTH_STATE_COOKIE]: "expected-state",
      [OAUTH_VERIFIER_COOKIE]: "verifier",
      [OAUTH_RETURN_TO_COOKIE]: "/positions?ticket=42",
    };
    mocks.cookies.mockResolvedValue({
      get: (name: string) =>
        cookieValues[name] === undefined ? undefined : { value: cookieValues[name] },
    });
    mocks.authenticateWithCode.mockResolvedValue(authResponse);

    const response = await GET(
      new NextRequest(
        "https://0.0.0.0:3000/auth/callback?code=authorization-code&state=expected-state",
      ),
    );

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe(
      "https://dashboard.example.com/positions?ticket=42",
    );
    expect(mocks.saveSession).toHaveBeenCalledWith(authResponse, publicCallback);
    expect(mocks.provisionDashboardAccess).toHaveBeenCalledWith(authResponse);
  });

  it("sends callback errors to the public sign-in page", async () => {
    const response = await GET(
      new NextRequest("https://0.0.0.0:3000/auth/callback?error=access_denied"),
    );

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe(
      "https://dashboard.example.com/sign-in?error=google_cancelled",
    );
  });

  it("sends a newly provisioned user directly to account setup", async () => {
    const cookieValues: Record<string, string> = {
      [OAUTH_STATE_COOKIE]: "expected-state",
      [OAUTH_VERIFIER_COOKIE]: "verifier",
      [OAUTH_RETURN_TO_COOKIE]: "/positions",
    };
    mocks.cookies.mockResolvedValue({
      get: (name: string) =>
        cookieValues[name] === undefined ? undefined : { value: cookieValues[name] },
    });
    mocks.authenticateWithCode.mockResolvedValue({
      accessToken: "access",
      refreshToken: "refresh",
      user: { id: "user_new", email: "new@example.com" },
    });
    mocks.provisionDashboardAccess.mockResolvedValue({
      active_account_id: null,
      setup_complete: false,
    });

    const response = await GET(
      new NextRequest(
        "https://dashboard.example.com/auth/callback?code=authorization-code&state=expected-state",
      ),
    );

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("https://dashboard.example.com/setup");
  });

  it("reports a disabled dashboard account separately from Google auth failures", async () => {
    const cookieValues: Record<string, string> = {
      [OAUTH_STATE_COOKIE]: "expected-state",
      [OAUTH_VERIFIER_COOKIE]: "verifier",
    };
    mocks.cookies.mockResolvedValue({
      get: (name: string) =>
        cookieValues[name] === undefined ? undefined : { value: cookieValues[name] },
    });
    mocks.authenticateWithCode.mockResolvedValue({
      accessToken: "access",
      refreshToken: "refresh",
      user: { id: "user_123", email: "trader@example.com" },
    });
    mocks.provisionDashboardAccess.mockRejectedValue(
      new ApiError("This dashboard account has been disabled.", 403, "access_disabled"),
    );

    const response = await GET(
      new NextRequest(
        "https://dashboard.example.com/auth/callback?code=authorization-code&state=expected-state",
      ),
    );

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe(
      "https://dashboard.example.com/sign-in?error=access_disabled",
    );
    expect(mocks.saveSession).not.toHaveBeenCalled();
  });
});
