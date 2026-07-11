import { getAuthToken } from "./auth-storage";
import { AUTH_MODE } from "./auth-mode";

type TokenProvider = () => Promise<string | null>;

let clerkTokenProvider: TokenProvider | null = null;
let betterAuthTokenProvider: TokenProvider | null = null;

export function setClerkTokenProvider(provider: TokenProvider | null) {
  clerkTokenProvider = provider;
}

export function setBetterAuthTokenProvider(provider: TokenProvider | null) {
  betterAuthTokenProvider = provider;
}

export async function getApiTokenForMode(
  mode: typeof AUTH_MODE,
  providers: {
    betterAuth?: TokenProvider | null;
    clerk?: TokenProvider | null;
    fallback?: TokenProvider;
  },
): Promise<string | null> {
  if (mode === "better-auth") {
    return providers.betterAuth ? providers.betterAuth() : null;
  }
  if (mode === "clerk") {
    return providers.clerk ? providers.clerk() : null;
  }
  return (providers.fallback ?? getAuthToken)();
}

export async function getApiToken(): Promise<string | null> {
  return getApiTokenForMode(AUTH_MODE, {
    betterAuth: betterAuthTokenProvider,
    clerk: clerkTokenProvider,
  });
}
