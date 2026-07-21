"use server";

import { getWorkOS, saveSession, signOut } from "@workos-inc/authkit-nextjs";
import { cookies } from "next/headers";
import {
  authErrorMessage,
  isValidEmail,
  normalizeEmail,
  OAUTH_INVITATION_COOKIE,
  OAUTH_RETURN_TO_COOKIE,
  OAUTH_STATE_COOKIE,
  OAUTH_VERIFIER_COOKIE,
  safeReturnTo,
  type AuthActionResult,
  type AuthMessageResult,
  type GoogleAuthUrlResult,
  workosRedirectUri,
} from "@/lib/workos-auth";

type SignInInput = {
  email: string;
  password: string;
  returnTo?: string;
  invitationToken?: string;
};

type SignUpInput = SignInInput & {
  name: string;
  confirmPassword: string;
};

type GoogleInput = {
  mode: "sign-in" | "sign-up";
  returnTo?: string;
  invitationToken?: string;
  loginHint?: string;
};

const oauthCookieOptions = {
  httpOnly: true,
  maxAge: 10 * 60,
  path: "/",
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
};

function workosClientId() {
  const clientId = process.env.WORKOS_CLIENT_ID?.trim();
  if (!clientId) throw new Error("WorkOS client ID is not configured");
  return clientId;
}

async function invitationEmail(invitationToken?: string) {
  const token = invitationToken?.trim();
  if (!token) return null;

  const invitation = await getWorkOS().userManagement.findInvitationByToken(token);
  if (invitation.state !== "pending") {
    throw new Error(`Invitation is ${invitation.state}`);
  }
  return invitation.email.trim().toLowerCase();
}

export async function signInWithPassword(input: SignInInput): Promise<AuthActionResult> {
  const email = normalizeEmail(input.email);
  if (!isValidEmail(email)) return { ok: false, error: "Enter a valid email address." };
  if (!input.password) return { ok: false, error: "Enter your password." };

  try {
    const invitedEmail = await invitationEmail(input.invitationToken);
    if (invitedEmail && email !== invitedEmail) {
      return { ok: false, error: `This invitation is only valid for ${invitedEmail}.` };
    }

    const authResponse = await getWorkOS().userManagement.authenticateWithPassword({
      clientId: workosClientId(),
      email,
      password: input.password,
      invitationToken: input.invitationToken?.trim() || undefined,
    });
    await saveSession(authResponse, workosRedirectUri());
    return { ok: true, redirectTo: safeReturnTo(input.returnTo) };
  } catch (error) {
    return {
      ok: false,
      error: authErrorMessage(error, "Unable to sign in. Check your details and try again."),
    };
  }
}

export async function signUpWithPassword(input: SignUpInput): Promise<AuthActionResult> {
  const email = normalizeEmail(input.email);
  const name = input.name.trim();
  if (!name) return { ok: false, error: "Enter your name." };
  if (!isValidEmail(email)) return { ok: false, error: "Enter a valid email address." };
  if (input.password.length < 10) {
    return { ok: false, error: "Use at least 10 characters for your password." };
  }
  if (input.password !== input.confirmPassword) {
    return { ok: false, error: "Passwords do not match." };
  }

  let createdUserId: string | null = null;
  try {
    const workos = getWorkOS();
    const invitedEmail = await invitationEmail(input.invitationToken);
    if (invitedEmail && email !== invitedEmail) {
      return { ok: false, error: `This invitation is only valid for ${invitedEmail}.` };
    }

    const existingUsers = await workos.userManagement.listUsers({ email, limit: 1 });
    if (existingUsers.data.length > 0) {
      return { ok: false, error: "An account already exists for this email. Sign in instead." };
    }

    const user = await workos.userManagement.createUser({
      email,
      name,
      password: input.password,
    });
    createdUserId = user.id;

    const authResponse = await workos.userManagement.authenticateWithPassword({
      clientId: workosClientId(),
      email,
      password: input.password,
      invitationToken: input.invitationToken?.trim() || undefined,
    });
    await saveSession(authResponse, workosRedirectUri());
    return { ok: true, redirectTo: safeReturnTo(input.returnTo) };
  } catch (error) {
    if (createdUserId) {
      try {
        await getWorkOS().userManagement.deleteUser(createdUserId);
      } catch {
        // Preserve the original sign-up failure; cleanup is best-effort.
      }
    }
    return {
      ok: false,
      error: authErrorMessage(error, "Unable to create your account. Check your details and try again."),
    };
  }
}

export async function getGoogleAuthUrl(input: GoogleInput): Promise<GoogleAuthUrlResult> {
  try {
    const invitedEmail = await invitationEmail(input.invitationToken);
    const { url, state, codeVerifier } =
      await getWorkOS().userManagement.getAuthorizationUrlWithPKCE({
        clientId: workosClientId(),
        provider: "GoogleOAuth",
        redirectUri: workosRedirectUri(),
        invitationToken: input.invitationToken?.trim() || undefined,
        loginHint: invitedEmail ?? (normalizeEmail(input.loginHint ?? "") || undefined),
      });

    const cookieStore = await cookies();
    cookieStore.set(OAUTH_STATE_COOKIE, state, oauthCookieOptions);
    cookieStore.set(OAUTH_VERIFIER_COOKIE, codeVerifier, oauthCookieOptions);
    cookieStore.set(OAUTH_RETURN_TO_COOKIE, safeReturnTo(input.returnTo), oauthCookieOptions);
    if (input.invitationToken?.trim()) {
      cookieStore.set(OAUTH_INVITATION_COOKIE, input.invitationToken.trim(), oauthCookieOptions);
    } else {
      cookieStore.delete(OAUTH_INVITATION_COOKIE);
    }

    return { ok: true, url };
  } catch (error) {
    return {
      ok: false,
      error: authErrorMessage(error, "Unable to start Google sign-in. Please try again."),
    };
  }
}

export async function requestPasswordReset(emailInput: string): Promise<AuthMessageResult> {
  const email = normalizeEmail(emailInput);
  if (!isValidEmail(email)) return { ok: false, error: "Enter a valid email address." };

  try {
    await getWorkOS().userManagement.createPasswordReset({ email });
  } catch {
    // Use the same response for unknown accounts and provider errors to avoid account enumeration.
  }

  return {
    ok: true,
    message: "If an account exists for this email, a password reset link is on its way.",
  };
}

export async function resetPassword(tokenInput: string, password: string): Promise<AuthActionResult> {
  const token = tokenInput.trim();
  if (!token) return { ok: false, error: "This password reset link is invalid." };
  if (password.length < 10) {
    return { ok: false, error: "Use at least 10 characters for your password." };
  }

  try {
    await getWorkOS().userManagement.resetPassword({ token, newPassword: password });
    return { ok: true, redirectTo: "/sign-in?reset=success" };
  } catch (error) {
    return {
      ok: false,
      error: authErrorMessage(error, "Unable to update your password. Request a new reset link."),
    };
  }
}

export async function signOutAction() {
  const origin = new URL(workosRedirectUri()).origin;
  await signOut({ returnTo: `${origin}/sign-in` });
}
