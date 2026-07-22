import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./api-error";

describe("dashboard access provisioning", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("provisions the authenticated WorkOS identity through the API session endpoint", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test");
    vi.stubEnv("DASHBOARD_PROXY_SECRET", "shared-secret");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user: { id: "user_123" },
          active_account_id: null,
          setup_complete: false,
        }),
        {
        status: 200,
        headers: { "content-type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { dashboardNeedsSetup, provisionDashboardAccess } = await import("./dashboard-access");

    const session = await provisionDashboardAccess({
      accessToken: "access-token",
      user: {
        id: "user_123",
        email: "trader@example.com",
      },
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(options.headers);
    expect(url).toBe("https://api.example.test/api/access/session");
    expect(options.method).toBe("POST");
    expect(headers.get("x-workos-user-id")).toBe("user_123");
    expect(headers.get("x-workos-user-email")).toBe("trader@example.com");
    expect(session).toMatchObject({ active_account_id: null, setup_complete: false });
    expect(dashboardNeedsSetup(session)).toBe(true);
  });

  it("preserves structured authorization errors", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test");
    vi.stubEnv("DASHBOARD_PROXY_SECRET", "shared-secret");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              code: "access_disabled",
              message: "This dashboard account has been disabled.",
            },
          }),
          { status: 403, headers: { "content-type": "application/json" } },
        ),
      ),
    );
    const { provisionDashboardAccess } = await import("./dashboard-access");

    const error = await provisionDashboardAccess({
      accessToken: "access-token",
      user: { id: "user_123", email: "trader@example.com" },
    }).catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, code: "access_disabled" });
  });
});
