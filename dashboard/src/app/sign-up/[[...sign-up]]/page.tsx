"use client";

import { SignUp } from "@clerk/nextjs";
import { AUTH_MODE } from "@/lib/auth-mode";
import { BetterAuthSignUp } from "@/components/auth/better-auth-sign-up";

export default function SignUpPage() {
  if (AUTH_MODE === "better-auth") {
    return <BetterAuthSignUp />;
  }
  if (AUTH_MODE !== "clerk") {
    return <AuthNotConfigured />;
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-bg-primary p-6">
      <SignUp signInUrl="/sign-in" fallbackRedirectUrl="/" />
    </main>
  );
}

function AuthNotConfigured() {
  return (
    <main className="grid min-h-dvh place-items-center bg-bg-primary p-6">
      <div className="w-full max-w-md rounded-xl border border-border-subtle bg-bg-secondary p-6">
        <p className="text-xs uppercase tracking-wider text-text-muted">Access</p>
        <h1 className="mt-2 text-xl font-semibold text-text-primary">Clerk is not configured</h1>
        <p className="mt-2 text-sm text-text-muted">
          Add Clerk publishable and secret keys before switching production to Clerk sign-up.
        </p>
      </div>
    </main>
  );
}
