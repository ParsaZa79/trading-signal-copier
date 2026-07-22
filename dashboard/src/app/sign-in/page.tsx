import { withAuth } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";
import { WorkOSSignInForm } from "@/components/auth/workos-sign-in-form";
import { safeReturnTo } from "@/lib/workos-auth";

interface SignInPageProps {
  searchParams: Promise<{
    error?: string;
    invitation_token?: string;
    reset?: string;
    returnTo?: string;
  }>;
}

const errorMessages: Record<string, string> = {
  access_disabled: "This dashboard account has been disabled. Ask an owner to restore access.",
  access_setup_failed:
    "Google sign-in succeeded, but dashboard setup is temporarily unavailable. Please try again.",
  auth_not_configured: "Authentication is not configured correctly.",
  google_auth_failed: "Google sign-in could not be completed. Please try again.",
  google_cancelled: "Google sign-in was cancelled.",
  oauth_state_mismatch: "That Google sign-in attempt expired. Please try again.",
};

export default async function SignInPage({ searchParams }: SignInPageProps) {
  const params = await searchParams;
  const returnTo = safeReturnTo(params.returnTo);
  const { user } = await withAuth();
  if (user) redirect(returnTo);

  return (
    <WorkOSSignInForm
      returnTo={returnTo}
      invitationToken={params.invitation_token?.trim() || undefined}
      initialError={params.error ? errorMessages[params.error] ?? "Unable to sign in." : null}
      resetComplete={params.reset === "success"}
    />
  );
}
