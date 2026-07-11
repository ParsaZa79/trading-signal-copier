type PublicEnvironment = Readonly<Record<string, string | undefined>>;

export type AuthMode = "better-auth" | "clerk" | "local";

function enabled(value: string | undefined) {
  return value?.trim().toLowerCase() === "true";
}

export function resolveAuthMode(environment: PublicEnvironment): AuthMode {
  if (enabled(environment.NEXT_PUBLIC_BETTER_AUTH_ENABLED)) return "better-auth";
  if (environment.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim()) return "clerk";
  return "local";
}

export function resolvePublicAuthConfig(environment: PublicEnvironment) {
  return {
    mode: resolveAuthMode(environment),
    openSignup: enabled(environment.NEXT_PUBLIC_OPEN_SIGNUP_ENABLED),
    turnstileSiteKey: environment.NEXT_PUBLIC_TURNSTILE_SITE_KEY?.trim() ?? "",
  } as const;
}

export const AUTH_CONFIG = resolvePublicAuthConfig({
  NEXT_PUBLIC_BETTER_AUTH_ENABLED: process.env.NEXT_PUBLIC_BETTER_AUTH_ENABLED,
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
  NEXT_PUBLIC_OPEN_SIGNUP_ENABLED: process.env.NEXT_PUBLIC_OPEN_SIGNUP_ENABLED,
  NEXT_PUBLIC_TURNSTILE_SITE_KEY: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY,
});
export const AUTH_MODE = AUTH_CONFIG.mode;
export const BETTER_AUTH_ENABLED = AUTH_MODE === "better-auth";
export const CLERK_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "";
export const CLERK_ENABLED = AUTH_MODE === "clerk";
