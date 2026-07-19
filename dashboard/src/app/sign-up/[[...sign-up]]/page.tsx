"use client";

import { SignUp } from "@clerk/nextjs";
import { useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { BetterAuthSignUp } from "@/components/auth/better-auth-sign-up";
import { AUTH_MODE } from "@/lib/auth-mode";

const clerkAppearance = {
  variables: {
    colorPrimary: "#829cff",
    colorBackground: "#050506",
    colorInputBackground: "#09090b",
    colorInputText: "#f7f7f9",
    colorText: "#f7f7f9",
    colorTextSecondary: "#85858d",
    borderRadius: "0.75rem",
  },
  elements: {
    rootBox: "w-full",
    cardBox: "w-full shadow-none",
    card: "w-full bg-transparent p-0 shadow-none",
    headerTitle: "text-[2.35rem] font-semibold tracking-[-0.045em] text-[#f7f7f9]",
    headerSubtitle: "text-base text-[#85858d]",
    formFieldLabel: "text-sm font-medium text-[#c7c7cc]",
    formFieldInput: "h-14 border-white/[0.11] bg-[#09090b] text-[15px] text-[#f7f7f9]",
    formButtonPrimary: "h-14 bg-[#829cff] text-[15px] font-semibold text-[#08090d] hover:bg-[#9aafff]",
    footer: "bg-transparent",
  },
} as const;

export default function SignUpPage() {
  const search = useSearchParams();
  const preview =
    process.env.NEXT_PUBLIC_COPY_TRADING_PREVIEW === "true" &&
    search.get("previewAuth") === "1";

  if (preview) {
    return <BetterAuthSignUp preview />;
  }
  if (AUTH_MODE === "better-auth") {
    return <BetterAuthSignUp />;
  }
  if (AUTH_MODE !== "clerk") {
    return <AuthNotConfigured />;
  }

  return (
    <AuthShell>
      <SignUp appearance={clerkAppearance} signInUrl="/sign-in" fallbackRedirectUrl="/" />
    </AuthShell>
  );
}

function AuthNotConfigured() {
  return (
    <AuthShell>
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#829cff]">Access</p>
      <h1 className="mt-4 text-[2.35rem] font-semibold leading-tight tracking-[-0.045em] text-[#f7f7f9]">
        Sign-up is not configured
      </h1>
      <p className="mt-4 max-w-[450px] text-base leading-relaxed text-[#92929a]">
        Add the authentication settings before opening account registration.
      </p>
    </AuthShell>
  );
}
