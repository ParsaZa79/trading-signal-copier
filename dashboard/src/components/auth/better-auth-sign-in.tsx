"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Loader2, LockKeyhole, Mail } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { AUTH_CONFIG } from "@/lib/auth-mode";
import { requestPasswordReset, safeAuthCallback, signInWithPassword } from "@/lib/better-auth-actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthShell } from "./auth-shell";
import { Turnstile } from "./turnstile";

const authFieldClass =
  "h-14 border-white/[0.11] bg-[#09090b]/80 text-[15px] placeholder:text-[#5f5f67] hover:border-white/[0.16] focus:border-[#829cff]/70 focus:ring-[#829cff]/15";
const authLabelClass = "mb-2.5 text-sm normal-case tracking-normal text-[#c7c7cc]";
const primaryButtonClass =
  "h-14 w-full bg-[#829cff] text-[15px] text-[#08090d] shadow-[0_10px_35px_rgba(92,120,255,0.18)] hover:bg-[#9aafff] focus-visible:ring-2 focus-visible:ring-[#aab9ff] focus-visible:ring-offset-2 focus-visible:ring-offset-[#050506]";

export function BetterAuthSignIn({ preview = false }: { preview?: boolean }) {
  const router = useRouter();
  const search = useSearchParams();
  const resetToken = search.get("token");
  const [forgot, setForgot] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState(preview ? "design-preview" : "");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (resetToken) return <ResetPassword token={resetToken} />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      if (preview) {
        setMessage("Preview only — authentication is not submitted.");
      } else if (!captcha) {
        setMessage("Complete the security verification.");
      } else if (forgot) {
        const result = await requestPasswordReset(
          authClient,
          email,
          `${window.location.origin}/sign-in`,
          captcha,
        );
        setMessage(result.message);
      } else {
        const result = await signInWithPassword(authClient, email, password, captcha);
        if (result.ok) {
          router.replace(safeAuthCallback(search.get("callbackURL")));
          router.refresh();
        } else {
          setMessage(result.message);
        }
      }
    } catch {
      setMessage(
        forgot
          ? "If an account exists, a reset link has been sent."
          : "Unable to sign in. Check your details and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <header>
        {forgot ? (
          <button
            type="button"
            onClick={() => {
              setForgot(false);
              setMessage(null);
            }}
            className="mb-7 inline-flex items-center gap-2 rounded-md text-sm text-[#9d9da5] hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to sign in
          </button>
        ) : null}
        <h1 id="auth-title" className="text-[2.35rem] font-semibold leading-tight tracking-[-0.045em] text-[#f7f7f9]">
          {forgot ? "Reset your password" : "Welcome back"}
        </h1>
        <p className="mt-2 text-lg text-[#85858d]">
          {forgot ? "We’ll send a reset link if the account exists." : "Sign in to continue"}
        </p>
      </header>

      <form className="mt-12 space-y-8 [@media(max-height:800px)]:space-y-6" onSubmit={submit} aria-labelledby="auth-title">
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

        {!forgot ? (
          <div>
            <Input
              label="Password"
              labelClassName={authLabelClass}
              className={authFieldClass}
              leadingIcon={<LockKeyhole className="h-4 w-4" strokeWidth={1.7} />}
              placeholder="Enter your password"
              type="password"
              autoComplete="current-password"
              required
              minLength={12}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                className="rounded-md text-sm font-medium text-[#829cff] hover:text-[#aab9ff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                onClick={() => {
                  setForgot(true);
                  setMessage(null);
                }}
              >
                Forgot password?
              </button>
            </div>
          </div>
        ) : null}

        {!preview ? <Turnstile siteKey={AUTH_CONFIG.turnstileSiteKey} onToken={setCaptcha} /> : null}

        {message ? (
          <p role="status" className="rounded-xl border border-white/[0.08] bg-white/[0.035] px-4 py-3 text-sm leading-relaxed text-[#aaaab1]">
            {message}
          </p>
        ) : null}

        <Button className={primaryButtonClass} variant="accent" type="submit" disabled={busy || !captcha}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
          {busy ? "Please wait…" : forgot ? "Send reset link" : "Sign in"}
        </Button>
      </form>

      {!forgot && (AUTH_CONFIG.openSignup || preview) ? (
        <p className="mt-6 text-center text-sm text-[#92929a]">
          New here?{" "}
          <Link
            className="rounded-md font-medium text-[#829cff] hover:text-[#aab9ff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
            href={preview ? "/sign-up?previewAuth=1" : "/sign-up"}
          >
            Create account
          </Link>
        </p>
      ) : null}
    </AuthShell>
  );
}

function ResetPassword({ token }: { token: string }) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const { error } = await authClient.resetPassword({ newPassword: password, token });
      if (error) throw new Error();
      setMessage("Password updated. You can now sign in.");
      window.setTimeout(() => router.replace("/sign-in"), 800);
    } catch {
      setMessage("This reset link is invalid or expired. Request a new one.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <header>
        <h1 id="reset-title" className="text-[2.35rem] font-semibold leading-tight tracking-[-0.045em] text-[#f7f7f9]">
          Choose a new password
        </h1>
        <p className="mt-2 text-lg text-[#85858d]">Use at least 12 characters.</p>
      </header>
      <form className="mt-12 space-y-6" onSubmit={submit} aria-labelledby="reset-title">
        <Input
          label="New password"
          labelClassName={authLabelClass}
          className={authFieldClass}
          leadingIcon={<LockKeyhole className="h-4 w-4" strokeWidth={1.7} />}
          placeholder="Enter a new password"
          type="password"
          autoComplete="new-password"
          minLength={12}
          maxLength={128}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {message ? <p role="status" className="text-sm text-[#aaaab1]">{message}</p> : null}
        <Button className={primaryButtonClass} variant="accent" type="submit" disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
          {busy ? "Updating…" : "Update password"}
        </Button>
      </form>
    </AuthShell>
  );
}
