import { timingSafeEqual } from "node:crypto";
import { getWorkOS, saveSession } from "@workos-inc/authkit-nextjs";
import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import {
  OAUTH_INVITATION_COOKIE,
  OAUTH_RETURN_TO_COOKIE,
  OAUTH_STATE_COOKIE,
  OAUTH_VERIFIER_COOKIE,
  safeReturnTo,
  workosRedirectUri,
} from "@/lib/workos-auth";
import { ApiError } from "@/lib/api-error";
import { dashboardNeedsSetup, provisionDashboardAccess } from "@/lib/dashboard-access";

function equalState(received: string | null, expected: string | undefined) {
  if (!received || !expected) return false;
  const receivedBuffer = Buffer.from(received);
  const expectedBuffer = Buffer.from(expected);
  return (
    receivedBuffer.length === expectedBuffer.length &&
    timingSafeEqual(receivedBuffer, expectedBuffer)
  );
}

function clearOAuthCookies(response: NextResponse) {
  for (const name of [
    OAUTH_STATE_COOKIE,
    OAUTH_VERIFIER_COOKIE,
    OAUTH_RETURN_TO_COOKIE,
    OAUTH_INVITATION_COOKIE,
  ]) {
    response.cookies.delete(name);
  }
  return response;
}

function signInError(code: string) {
  const url = new URL("/sign-in", workosRedirectUri());
  url.searchParams.set("error", code);
  return clearOAuthCookies(NextResponse.redirect(url, 303));
}

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");
  const state = requestUrl.searchParams.get("state");
  if (requestUrl.searchParams.get("error") || !code) return signInError("google_cancelled");

  const cookieStore = await cookies();
  const expectedState = cookieStore.get(OAUTH_STATE_COOKIE)?.value;
  const codeVerifier = cookieStore.get(OAUTH_VERIFIER_COOKIE)?.value;
  const returnTo = safeReturnTo(cookieStore.get(OAUTH_RETURN_TO_COOKIE)?.value);
  const invitationToken = cookieStore.get(OAUTH_INVITATION_COOKIE)?.value;
  if (!equalState(state, expectedState) || !codeVerifier) {
    return signInError("oauth_state_mismatch");
  }

  const clientId = process.env.WORKOS_CLIENT_ID?.trim();
  if (!clientId) return signInError("auth_not_configured");

  try {
    const redirectUri = workosRedirectUri();
    const authResponse = await getWorkOS().userManagement.authenticateWithCode({
      clientId,
      code,
      codeVerifier,
      invitationToken,
    });
    const dashboardSession = await provisionDashboardAccess(authResponse);
    await saveSession(authResponse, redirectUri);
    const destination = dashboardNeedsSetup(dashboardSession) ? "/setup" : returnTo;
    return clearOAuthCookies(NextResponse.redirect(new URL(destination, redirectUri), 303));
  } catch (error) {
    if (error instanceof ApiError) {
      return signInError(error.code === "access_disabled" ? "access_disabled" : "access_setup_failed");
    }
    return signInError("google_auth_failed");
  }
}
