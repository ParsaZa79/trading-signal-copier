import { beforeEach, describe, expect, it, vi } from "vitest";
import { getBetterAuthJwt } from "./auth-client";

describe("Better Auth browser token retrieval", () => {
  const token = vi.fn();

  beforeEach(() => {
    token.mockReset();
  });

  it("fetches bearer tokens with the browser cache disabled", async () => {
    token.mockResolvedValue({
      data: { token: "memory-only-token" },
      error: null,
    });

    await expect(getBetterAuthJwt({ token })).resolves.toBe("memory-only-token");
    expect(token).toHaveBeenCalledWith({
      fetchOptions: { cache: "no-store" },
    });
  });

  it("does not expose a token when Better Auth returns an error", async () => {
    token.mockResolvedValue({
      data: null,
      error: { status: 401 },
    });

    await expect(getBetterAuthJwt({ token })).resolves.toBeNull();
  });
});
