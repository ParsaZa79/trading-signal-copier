"use client";

import { SignIn } from "@clerk/nextjs";
import { CLERK_ENABLED } from "@/lib/auth-mode";

export default function SignInPage() {
  if (!CLERK_ENABLED) {
    return <AuthNotConfigured />;
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-bg-primary p-6">
      <SignIn signUpUrl="/sign-up" fallbackRedirectUrl="/" />
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
          Add Clerk publishable and secret keys before switching production to Clerk sign-in.
        </p>
      </div>
    </main>
  );
}
