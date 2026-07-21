export type AuthActionResult =
  | { ok: true; redirectTo: string }
  | { ok: false; error: string };

export type AuthMessageResult =
  | { ok: true; message: string }
  | { ok: false; error: string };

export type GoogleAuthUrlResult =
  | { ok: true; url: string }
  | { ok: false; error: string };

export const OAUTH_STATE_COOKIE = "sc_workos_oauth_state";
export const OAUTH_VERIFIER_COOKIE = "sc_workos_oauth_verifier";
export const OAUTH_RETURN_TO_COOKIE = "sc_workos_oauth_return_to";
export const OAUTH_INVITATION_COOKIE = "sc_workos_oauth_invitation";

export function workosRedirectUri(
  value = process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI,
) {
  const candidate = value?.trim();
  if (!candidate) throw new Error("WorkOS redirect URI is not configured");

  const url = new URL(candidate);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("WorkOS redirect URI must use HTTP or HTTPS");
  }

  return url.toString();
}

export function normalizeEmail(value: string) {
  return value.trim().toLowerCase();
}

export function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizeEmail(value));
}

export function safeReturnTo(value?: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return "/";
  }

  return value;
}

export function authErrorMessage(error: unknown, fallback: string) {
  if (!(error instanceof Error)) return fallback;

  const message = error.message.toLowerCase();
  if (message.includes("invalid email or password") || message.includes("invalid credentials")) {
    return "Invalid email or password.";
  }
  if (message.includes("already exists") || message.includes("already registered")) {
    return "An account already exists for this email. Sign in instead.";
  }
  if (
    message.includes("password policy") ||
    message.includes("password requirement") ||
    message.includes("password strength") ||
    message.includes("compromised") ||
    message.includes("breach") ||
    message.includes("weak password")
  ) {
    return "Choose a stronger password that has not appeared in a known data breach.";
  }
  if (message.includes("invitation") && (message.includes("expired") || message.includes("invalid"))) {
    return "This invitation is invalid or has expired. Ask an administrator for a new one.";
  }
  if (message.includes("reset") && (message.includes("expired") || message.includes("invalid"))) {
    return "This password reset link is invalid or has expired. Request a new one.";
  }

  return fallback;
}
