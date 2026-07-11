"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { AUTH_CONFIG } from "@/lib/auth-mode";
import { requestPasswordReset, safeAuthCallback, signInWithPassword } from "@/lib/better-auth-actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Turnstile } from "./turnstile";

const panel = "w-full max-w-md rounded-xl border border-border-subtle bg-bg-secondary p-6";

export function BetterAuthSignIn() {
  const router = useRouter();
  const search = useSearchParams();
  const resetToken = search.get("token");
  const [forgot, setForgot] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (resetToken) return <ResetPassword token={resetToken} />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      if (!captcha) {
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
      setMessage(forgot ? "If an account exists, a reset link has been sent." : "Unable to sign in. Check your details and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-bg-primary p-6">
      <section className={panel} aria-labelledby="auth-title">
        <h1 id="auth-title" className="text-xl font-semibold text-text-primary">{forgot ? "Reset your password" : "Sign in"}</h1>
        <p className="mt-2 text-sm text-text-muted">{forgot ? "We will send a reset link if the account exists." : "Use your verified Strategy Lab account."}</p>
        <form className="mt-5 space-y-4" onSubmit={submit}>
          <Input label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          {!forgot && <Input label="Password" type="password" autoComplete="current-password" required minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} />}
          <Turnstile siteKey={AUTH_CONFIG.turnstileSiteKey} onToken={setCaptcha} />
          {message && <p role="status" className="text-sm text-text-muted">{message}</p>}
          <Button className="w-full" variant="accent" type="submit" disabled={busy || !captcha}>{busy ? "Please wait…" : forgot ? "Send reset link" : "Sign in"}</Button>
        </form>
        <button type="button" className="mt-4 text-sm text-accent underline" onClick={() => { setForgot(!forgot); setMessage(null); }}>{forgot ? "Back to sign in" : "Forgot password?"}</button>
        {AUTH_CONFIG.openSignup && <p className="mt-4 text-sm text-text-muted">Need an account? <Link className="text-accent underline" href="/sign-up">Sign up</Link></p>}
      </section>
    </main>
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
      setTimeout(() => router.replace("/sign-in"), 800);
    } catch {
      setMessage("This reset link is invalid or expired. Request a new one.");
    } finally { setBusy(false); }
  }
  return <main className="grid min-h-dvh place-items-center bg-bg-primary p-6"><section className={panel} aria-labelledby="reset-title"><h1 id="reset-title" className="text-xl font-semibold text-text-primary">Choose a new password</h1><form className="mt-5 space-y-4" onSubmit={submit}><Input label="New password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={(e) => setPassword(e.target.value)} />{message && <p role="status" className="text-sm text-text-muted">{message}</p>}<Button className="w-full" variant="accent" type="submit" disabled={busy}>{busy ? "Updating…" : "Update password"}</Button></form></section></main>;
}
