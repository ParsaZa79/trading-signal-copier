import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  OAUTH_RETURN_TO_COOKIE,
  OAUTH_STATE_COOKIE,
  OAUTH_VERIFIER_COOKIE,
} from "@/lib/workos-auth";

const mocks = vi.hoisted(() => ({
  authenticateWithCode: vi.fn(),
  cookies: vi.fn(),
  saveSession: vi.fn(),
}));

vi.mock("next/headers", () => ({ cookies: mocks.cookies }));
vi.mock("@workos-inc/authkit-nextjs", () => ({
  getWorkOS: () => ({
    userManagement: { authenticateWithCode: mocks.authenticateWithCode },
  }),
  saveSession: mocks.saveSession,
}));

import { GET } from "./route";

const publicCallback = "https://dashboard.example.com/auth/callback";

describe("WorkOS Google callback", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_WORKOS_REDIRECT_URI", publicCallback);
    vi.stubEnv("WORKOS_CLIENT_ID", "client_test");
    mocks.authenticateWithCode.mockReset();
    mocks.cookies.mockReset();
    mocks.saveSession.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("redirects to the public dashboard when Docker reports its internal host", async () => {
    const authResponse = { accessToken: "access", refreshToken: "refresh" };
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
});
