"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, Loader2, LockKeyhole, Mail, UserRound } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { AUTH_CONFIG } from "@/lib/auth-mode";
import { authCaptchaHeaders } from "@/lib/better-auth-actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthShell } from "./auth-shell";
import { Turnstile } from "./turnstile";

const authFieldClass =
  "h-14 border-white/[0.11] bg-[#09090b]/80 text-[15px] placeholder:text-[#5f5f67] hover:border-white/[0.16] focus:border-[#829cff]/70 focus:ring-[#829cff]/15";
const authLabelClass = "mb-2.5 text-sm normal-case tracking-normal text-[#c7c7cc]";
const primaryButtonClass =
  "h-14 w-full bg-[#829cff] text-[15px] text-[#08090d] shadow-[0_10px_35px_rgba(92,120,255,0.18)] hover:bg-[#9aafff] focus-visible:ring-2 focus-visible:ring-[#aab9ff] focus-visible:ring-offset-2 focus-visible:ring-offset-[#050506]";

export function BetterAuthSignUp({ preview = false }: { preview?: boolean }) {
  if (!AUTH_CONFIG.openSignup && !preview) {
    return (
      <AuthShell>
        <LockKeyhole className="h-10 w-10 text-[#829cff]" strokeWidth={1.7} aria-hidden="true" />
        <h1 id="signup-title" className="mt-7 text-[2.35rem] font-semibold leading-tight tracking-[-0.045em] text-[#f7f7f9]">
          Account registration is closed
        </h1>
        <p className="mt-4 max-w-[450px] text-base leading-relaxed text-[#92929a]">
          Ask an administrator for access, then sign in with your verified email.
        </p>
        <Link
          href={preview ? "/sign-in?previewAuth=1" : "/sign-in"}
          className="mt-10 flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-[#829cff] text-[15px] font-semibold text-[#08090d] shadow-[0_10px_35px_rgba(92,120,255,0.18)] hover:bg-[#9aafff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#aab9ff] focus-visible:ring-offset-2 focus-visible:ring-offset-[#050506]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to sign in
        </Link>
      </AuthShell>
    );
  }

  return <OpenSignUp preview={preview} />;
}

function OpenSignUp({ preview }: { preview: boolean }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState(preview ? "design-preview" : "");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (preview) {
      setMessage("Preview only — account creation is not submitted.");
      return;
    }
    if (!captcha) return setMessage("Complete the security verification.");
    setBusy(true);
    try {
      const { error } = await authClient.signUp.email(
        { name: name.trim(), email: email.trim(), password },
        { headers: authCaptchaHeaders(captcha) },
      );
      setMessage(
        error
          ? "Unable to create an account. Check your details and try again."
          : "Check your email to verify your account before signing in.",
      );
    } catch {
      setMessage("Unable to create an account. Check your details and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <header>
        <h1 id="signup-title" className="text-[2.35rem] font-semibold leading-tight tracking-[-0.045em] text-[#f7f7f9]">
          Create your account
        </h1>
        <p className="mt-2 text-lg text-[#85858d]">Start with a few simple details</p>
      </header>

      <form className="mt-10 space-y-5" onSubmit={submit} aria-labelledby="signup-title">
        <Input
          label="Your name"
          labelClassName={authLabelClass}
          className={authFieldClass}
          leadingIcon={<UserRound className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="How should we address you?"
          autoComplete="name"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Input
          label="Email address"
          labelClassName={authLabelClass}
          className={authFieldClass}
          leadingIcon={<Mail className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="you@example.com"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <div>
          <Input
            label="Password"
            labelClassName={authLabelClass}
            className={authFieldClass}
            leadingIcon={<LockKeyhole className="h-4 w-4" strokeWidth={1.7} />}
            placeholder="Create a secure password"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p className="mt-2 text-xs text-[#73737b]">Use at least 12 characters.</p>
        </div>

        {!preview ? <Turnstile siteKey={AUTH_CONFIG.turnstileSiteKey} onToken={setCaptcha} /> : null}

        {message ? (
          <p role="status" className="rounded-xl border border-white/[0.08] bg-white/[0.035] px-4 py-3 text-sm leading-relaxed text-[#aaaab1]">
            {message}
          </p>
        ) : null}

        <Button className={primaryButtonClass} variant="accent" type="submit" disabled={busy || !captcha}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
          {busy ? "Creating…" : "Create account"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-[#92929a]">
        Already have an account?{" "}
        <Link
          className="rounded-md font-medium text-[#829cff] hover:text-[#aab9ff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          href={preview ? "/sign-in?previewAuth=1" : "/sign-in"}
        >
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
