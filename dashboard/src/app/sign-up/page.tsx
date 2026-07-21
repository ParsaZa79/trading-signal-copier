import { withAuth } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";
import { WorkOSSignUpForm } from "@/components/auth/workos-sign-up-form";
import { safeReturnTo } from "@/lib/workos-auth";

interface SignUpPageProps {
  searchParams: Promise<{
    invitation_token?: string;
    returnTo?: string;
  }>;
}

export default async function SignUpPage({ searchParams }: SignUpPageProps) {
  const params = await searchParams;
  const returnTo = safeReturnTo(params.returnTo);
  const { user } = await withAuth();
  if (user) redirect(returnTo);

  return (
    <WorkOSSignUpForm
      returnTo={returnTo}
      invitationToken={params.invitation_token?.trim() || undefined}
    />
  );
}
