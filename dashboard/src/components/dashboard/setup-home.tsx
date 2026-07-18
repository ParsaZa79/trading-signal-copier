"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Check,
  ChevronDown,
  Eye,
  LockKeyhole,
  PlugZap,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import { AnimatedSection, PageContainer } from "@/components/motion";
import { cn } from "@/lib/utils";
import type { AuthSession } from "@/lib/auth-storage";

interface SetupHomeProps {
  session: AuthSession;
}

const previewRows = [
  { label: "Account balance", icon: WalletCards },
  { label: "Open trades", icon: Activity },
  { label: "Today’s result", icon: BarChart3 },
];

function fullDate() {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(new Date());
}

export function SetupHome({ session }: SetupHomeProps) {
  const [showConnectionHelp, setShowConnectionHelp] = useState(false);
  const hasAccountDetails = session.accounts.length > 0 && Boolean(session.activeAccountId);
  const title = hasAccountDetails
    ? "Finish connecting your trading account"
    : "Set up your first trading account";
  const description = hasAccountDetails
    ? "Connect MT5 to see your balance and begin safely."
    : "Add your account details, then connect MT5 when you’re ready.";

  const steps = [
    {
      label: "Account details",
      state: hasAccountDetails ? "complete" : "current",
    },
    {
      label: "Connect MT5",
      state: hasAccountDetails ? "current" : "upcoming",
    },
    { label: "Choose safety limits", state: "upcoming" },
  ] as const;

  return (
    <PageContainer className="mx-auto max-w-[1320px] space-y-5">
      <AnimatedSection>
        <p className="text-sm text-text-muted">{fullDate()}</p>
      </AnimatedSection>

      <AnimatedSection>
        <section className="overflow-hidden rounded-[20px] border border-border-default bg-bg-secondary/45 shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
          <div className="grid min-h-[410px] lg:grid-cols-[0.9fr_1.35fr]">
            <div className="flex flex-col justify-center px-6 py-10 sm:px-10 lg:px-12">
              <span className="flex h-16 w-16 items-center justify-center rounded-full border border-accent/50 bg-accent/5 text-accent shadow-[0_0_36px_rgba(138,180,255,0.08)]">
                <PlugZap className="h-7 w-7" strokeWidth={1.7} />
              </span>
              <h1 className="mt-7 max-w-xl text-3xl font-semibold leading-[1.12] tracking-[-0.035em] text-text-primary sm:text-[40px]">
                {title}
              </h1>
              <p className="mt-4 max-w-md text-base leading-7 text-text-secondary">
                {description}
              </p>
              <Link
                href="/setup"
                className="mt-7 inline-flex h-14 w-full max-w-[415px] items-center justify-center gap-2 rounded-xl border border-accent-light/30 bg-accent px-5 text-base font-semibold text-bg-primary shadow-[0_12px_30px_rgba(91,141,239,0.18)] transition-[background-color,transform,box-shadow] hover:bg-accent-light hover:shadow-[0_16px_36px_rgba(91,141,239,0.24)] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-light focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary"
              >
                <PlugZap className="h-5 w-5" />
                {hasAccountDetails ? "Continue account setup" : "Start account setup"}
                <ArrowRight className="h-4 w-4" />
              </Link>
              <button
                type="button"
                aria-expanded={showConnectionHelp}
                onClick={() => setShowConnectionHelp((current) => !current)}
                className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/5 hover:text-accent-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
              >
                Learn how connection works
                <ChevronDown
                  className={cn(
                    "h-4 w-4 transition-transform",
                    showConnectionHelp && "rotate-180"
                  )}
                />
              </button>
              {showConnectionHelp && (
                <p className="mt-1 max-w-md rounded-xl border border-border-subtle bg-bg-tertiary/45 px-4 py-3 text-xs leading-5 text-text-secondary">
                  Your MT5 connection lets the dashboard read account balances and trade updates. Credentials stay tied to this account and are never shown here after setup.
                </p>
              )}
            </div>

            <div className="flex items-center px-6 py-8 sm:px-10 lg:px-8 xl:px-12">
              <ol className="grid w-full gap-3 rounded-2xl border border-border-subtle bg-bg-primary/30 p-5 sm:grid-cols-3 sm:gap-0 sm:p-8">
                {steps.map((step, index) => (
                  <li key={step.label} className="relative flex min-w-0 items-center gap-3 sm:flex-col sm:text-center">
                    {index > 0 && (
                      <span
                        aria-hidden="true"
                        className="absolute right-1/2 top-5 hidden h-px w-full bg-border-default sm:block"
                      />
                    )}
                    <span
                      className={cn(
                        "relative z-10 flex h-11 w-11 shrink-0 items-center justify-center rounded-full border bg-bg-primary text-base font-medium",
                        step.state === "complete" && "border-success text-success",
                        step.state === "current" && "border-accent text-accent shadow-[0_0_24px_rgba(138,180,255,0.10)]",
                        step.state === "upcoming" && "border-border-default text-text-muted"
                      )}
                    >
                      {step.state === "complete" ? <Check className="h-5 w-5" /> : index + 1}
                    </span>
                    <span className="relative z-10 min-w-0 bg-bg-primary/0 sm:mt-4 sm:px-2">
                      <span className="block truncate text-sm font-medium text-text-primary sm:whitespace-normal">
                        {step.label}
                      </span>
                      <span
                        className={cn(
                          "mt-1 block text-xs capitalize",
                          step.state === "complete" && "text-success",
                          step.state === "current" && "text-accent",
                          step.state === "upcoming" && "text-text-muted"
                        )}
                      >
                        {step.state}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>
      </AnimatedSection>

      <AnimatedSection className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-[20px] border border-border-default bg-bg-secondary/40 p-5 sm:p-7">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-border-subtle bg-bg-tertiary/70 text-accent">
              <Eye className="h-5 w-5" />
            </span>
            <h2 className="text-lg font-semibold text-text-primary">What you’ll see here</h2>
          </div>
          <div className="mt-5 divide-y divide-border-subtle">
            {previewRows.map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-3 py-4 first:pt-0 last:pb-0">
                <Icon className="h-5 w-5 text-accent" strokeWidth={1.7} />
                <span className="flex-1 text-sm text-text-secondary">{label}</span>
                <span className="font-mono text-base tracking-[0.18em] text-text-muted">— —</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[20px] border border-border-default bg-bg-secondary/40 p-5 sm:p-7">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-border-subtle bg-bg-tertiary/70 text-accent">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <h2 className="text-lg font-semibold text-text-primary">Safety first</h2>
          </div>
          <div className="mt-6 space-y-5">
            <div className="flex gap-3">
              <BarChart3 className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
              <div>
                <p className="text-sm font-medium text-text-primary">Try copying without real money</p>
                <p className="mt-1 text-sm leading-6 text-text-muted">Paper mode lets you see how copied trades behave first.</p>
              </div>
            </div>
            <div className="flex gap-3">
              <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
              <div>
                <p className="text-sm font-medium text-text-primary">Live copying stays off by default</p>
                <p className="mt-1 text-sm leading-6 text-text-muted">You review your loss limits and disclosures before enabling it.</p>
              </div>
            </div>
          </div>
        </section>
      </AnimatedSection>
    </PageContainer>
  );
}
