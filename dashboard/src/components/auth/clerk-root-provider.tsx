"use client";

import { ClerkProvider } from "@clerk/nextjs";
import type { ReactNode } from "react";
import { CLERK_ENABLED, CLERK_PUBLISHABLE_KEY } from "@/lib/auth-mode";

export function ClerkRootProvider({ children }: { children: ReactNode }) {
  if (!CLERK_ENABLED) {
    return <>{children}</>;
  }

  return (
    <ClerkProvider
      publishableKey={CLERK_PUBLISHABLE_KEY}
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      afterSignOutUrl="/sign-in"
    >
      {children}
    </ClerkProvider>
  );
}
