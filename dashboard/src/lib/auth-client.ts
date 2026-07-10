"use client";

import { createAuthClient } from "better-auth/react";
import { adminClient, jwtClient } from "better-auth/client/plugins";
import { authAccessControl, authRoles } from "./auth/permissions";

export const authClient = createAuthClient({
  plugins: [
    adminClient({
      ac: authAccessControl,
      roles: authRoles,
    }),
    jwtClient(),
  ],
});

type TokenClient = Pick<typeof authClient, "token">;

/**
 * Fetch a short-lived FastAPI bearer token without persisting it in browser
 * storage. Callers own the returned in-memory value.
 */
export async function getBetterAuthJwt(
  client: TokenClient = authClient,
): Promise<string | null> {
  const { data, error } = await client.token({
    fetchOptions: { cache: "no-store" },
  });
  if (error) {
    return null;
  }
  return data?.token ?? null;
}
