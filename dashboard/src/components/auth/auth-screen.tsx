"use client";

import { useState } from "react";
import { LockKeyhole, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login, setupAdmin } from "@/lib/api";
import type { AuthSession } from "@/lib/auth-storage";

interface AuthScreenProps {
  setupRequired: boolean;
  onAuthenticated: (session: AuthSession) => void;
}

export function AuthScreen({ setupRequired, onAuthenticated }: AuthScreenProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const session = setupRequired
        ? await setupAdmin(email, password)
        : await login(email, password);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-bg-primary flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent/15 border border-accent/30 flex items-center justify-center">
            <LockKeyhole className="w-5 h-5 text-accent" />
          </div>
          <div>
            <p className="text-lg font-semibold text-text-primary">
              {setupRequired ? "Create Admin" : "Sign In"}
            </p>
            <p className="text-xs text-text-muted">Signal Copier Dashboard</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={setupRequired ? "new-password" : "current-password"}
            required
          />

          {error && (
            <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2">
              <p className="text-xs text-danger">{error}</p>
            </div>
          )}

          <Button type="submit" variant="accent" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{setupRequired ? "Create Account" : "Sign In"}</span>
          </Button>
        </form>
      </div>
    </main>
  );
}
