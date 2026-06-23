import { getAuthToken } from "./auth-storage";
import { CLERK_ENABLED } from "./auth-mode";

type TokenProvider = () => Promise<string | null>;

let clerkTokenProvider: TokenProvider | null = null;

export function setClerkTokenProvider(provider: TokenProvider | null) {
  clerkTokenProvider = provider;
}

export async function getApiToken(): Promise<string | null> {
  if (CLERK_ENABLED && clerkTokenProvider) {
    return clerkTokenProvider();
  }
  return getAuthToken();
}
