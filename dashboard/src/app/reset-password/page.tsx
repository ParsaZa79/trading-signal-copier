import { WorkOSResetPasswordForm } from "@/components/auth/workos-reset-password-form";

interface ResetPasswordPageProps {
  searchParams: Promise<{ token?: string }>;
}

export default async function ResetPasswordPage({ searchParams }: ResetPasswordPageProps) {
  const { token = "" } = await searchParams;
  return <WorkOSResetPasswordForm token={token} />;
}
