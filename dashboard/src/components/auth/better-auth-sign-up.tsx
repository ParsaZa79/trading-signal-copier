"use client";

import Link from "next/link";
import { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { AUTH_CONFIG } from "@/lib/auth-mode";
import { authCaptchaHeaders } from "@/lib/better-auth-actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Turnstile } from "./turnstile";

export function BetterAuthSignUp() {
  if (!AUTH_CONFIG.openSignup) {
    return <main className="grid min-h-dvh place-items-center bg-bg-primary p-6"><section className="w-full max-w-md rounded-xl border border-border-subtle bg-bg-secondary p-6" aria-labelledby="signup-title"><h1 id="signup-title" className="text-xl font-semibold text-text-primary">Account registration is closed</h1><p className="mt-2 text-sm text-text-muted">Ask an administrator for access, then sign in with your verified email.</p><Link href="/sign-in" className="mt-5 inline-block text-sm text-accent underline">Back to sign in</Link></section></main>;
  }
  return <OpenSignUp />;
}

function OpenSignUp() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!captcha) return setMessage("Complete the security verification.");
    setBusy(true);
    try {
      const { error } = await authClient.signUp.email(
        { name: name.trim(), email: email.trim(), password },
        { headers: authCaptchaHeaders(captcha) },
      );
      setMessage(error ? "Unable to create an account. Check your details and try again." : "Check your email to verify your account before signing in.");
    } catch {
      setMessage("Unable to create an account. Check your details and try again.");
    } finally { setBusy(false); }
  }
  return <main className="grid min-h-dvh place-items-center bg-bg-primary p-6"><section className="w-full max-w-md rounded-xl border border-border-subtle bg-bg-secondary p-6" aria-labelledby="signup-title"><h1 id="signup-title" className="text-xl font-semibold text-text-primary">Create account</h1><form className="mt-5 space-y-4" onSubmit={submit}><Input label="Name" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} /><Input label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /><Input label="Password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={(e) => setPassword(e.target.value)} /><Turnstile siteKey={AUTH_CONFIG.turnstileSiteKey} onToken={setCaptcha} />{message && <p role="status" className="text-sm text-text-muted">{message}</p>}<Button className="w-full" variant="accent" type="submit" disabled={busy || !captcha}>{busy ? "Creating…" : "Create account"}</Button></form><Link href="/sign-in" className="mt-4 inline-block text-sm text-accent underline">Back to sign in</Link></section></main>;
}
