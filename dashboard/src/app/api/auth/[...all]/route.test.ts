import { afterEach, describe, expect, it, vi } from "vitest";
import * as route from "./route";

const authGlobal = globalThis as typeof globalThis & {
  strategyLabBetterAuth?: {
    handler(request: Request): Promise<Response>;
  };
};

describe("Better Auth catch-all route", () => {
  afterEach(() => {
    delete authGlobal.strategyLabBetterAuth;
  });

  it("exports every method supported by the dormant Clerk proxy", () => {
    expect(route.GET).toBeTypeOf("function");
    expect(route.POST).toBeTypeOf("function");
    expect(route.PUT).toBeTypeOf("function");
    expect(route.PATCH).toBeTypeOf("function");
    expect(route.DELETE).toBeTypeOf("function");
  });

  it("makes the actual GET token export private and non-cacheable", async () => {
    authGlobal.strategyLabBetterAuth = {
      handler: vi.fn(async () =>
        Response.json(
          { token: "short-lived-secret" },
          { headers: { "Cache-Control": "public, max-age=60" } },
        ),
      ),
    };

    const response = await route.GET(
      new Request("https://dashboard.example.test/api/auth/token") as never,
      { params: Promise.resolve({ all: ["token"] }) },
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("pragma")).toBe("no-cache");
  });
});
