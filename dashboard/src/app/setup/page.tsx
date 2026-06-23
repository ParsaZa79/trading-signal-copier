"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  Check,
  ExternalLink,
  Loader2,
  Server,
  WalletCards,
} from "lucide-react";
import {
  PageHeader,
  PageLoading,
  PanelBody,
  PanelHeader,
  SectionPanel,
} from "@/components/layout";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { AnimatedSection, PageContainer } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  activateAccount,
  completeAccountSetup,
  connectMT5,
  createAccount,
  getBotConfig,
  getMe,
  saveBotConfig,
} from "@/lib/api";

const EMPTY_CONFIG = {
  MT5_LOGIN: "",
  MT5_PASSWORD: "",
  MT5_SERVER: "",
};

type SetupConfig = typeof EMPTY_CONFIG;

export default function SetupPage() {
  const router = useRouter();
  const { session, setSession } = useDashboard();
  const [accountName, setAccountName] = useState("Live Account");
  const [config, setConfig] = useState<SetupConfig>(EMPTY_CONFIG);
  const [configuredSecrets, setConfiguredSecrets] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(Boolean(session.activeAccountId));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeAccount = useMemo(
    () => session.accounts.find((account) => account.id === session.activeAccountId),
    [session.accounts, session.activeAccountId]
  );

  useEffect(() => {
    if (activeAccount?.name) {
      setAccountName(activeAccount.name);
    }
  }, [activeAccount?.name]);

  useEffect(() => {
    if (!session.activeAccountId) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    async function loadConfig() {
      setIsLoading(true);
      try {
        const result = await getBotConfig();
        if (cancelled || !result.success) return;
        setConfig({
          MT5_LOGIN: result.config.MT5_LOGIN || "",
          MT5_PASSWORD: result.config.MT5_PASSWORD || "",
          MT5_SERVER: result.config.MT5_SERVER || "",
        });
        setConfiguredSecrets(result.configuredSecrets || []);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load setup state");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadConfig();
    return () => {
      cancelled = true;
    };
  }, [session.activeAccountId]);

  const updateField = (key: keyof SetupConfig, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setError(null);
    setMessage(null);
  };

  const validate = () => {
    const missing: string[] = [];
    if (!session.activeAccountId && !accountName.trim()) missing.push("account name");
    if (!config.MT5_LOGIN.trim() || Number.isNaN(Number(config.MT5_LOGIN))) {
      missing.push("MT5 login");
    }
    if (!config.MT5_PASSWORD.trim() && !configuredSecrets.includes("MT5_PASSWORD")) {
      missing.push("MT5 password");
    }
    if (!config.MT5_SERVER.trim()) missing.push("MT5 server");
    return missing;
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const missing = validate();
    if (missing.length > 0) {
      setError(`Missing required setup: ${missing.join(", ")}.`);
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setMessage("Saving account setup...");

    try {
      if (!session.activeAccountId) {
        const created = await createAccount(accountName.trim());
        const activated = await activateAccount(created.account.id);
        setSession({
          ...session,
          accounts: activated.accounts,
          activeAccountId: activated.active_account_id,
          setupComplete: false,
        });
      }

      const saved = await saveBotConfig(config);
      setConfiguredSecrets(saved.configuredSecrets || []);

      setMessage("Testing broker connection...");
      const mt5Result = await connectMT5(config);
      if (!mt5Result.success || !mt5Result.connected) {
        throw new Error(mt5Result.error || mt5Result.health?.error || "Broker connection failed");
      }

      setMessage("Finalizing setup...");
      await completeAccountSetup();
      const refreshed = await getMe();
      setSession(refreshed);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not complete setup");
      setMessage(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <PageContainer className="max-w-[1100px]">
        <PageLoading label="Loading account setup..." />
      </PageContainer>
    );
  }

  return (
    <PageContainer className="max-w-[1100px]">
      <AnimatedSection>
        <PageHeader
          meta="Account setup"
          title="Connect your broker"
          description="Complete this once for each trading account. The Telegram signal source is managed by the platform."
        />
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">
        <form onSubmit={handleSubmit} className="space-y-4">
          <SectionPanel>
            <PanelHeader
              eyebrow="Account"
              title="Trading account"
              description="This name is only used inside your dashboard"
              action={<WalletCards className="h-5 w-5 text-accent" />}
            />
            <PanelBody>
              <Input
                label="Account name"
                value={accountName}
                onChange={(event) => setAccountName(event.target.value)}
                disabled={Boolean(session.activeAccountId) || isSubmitting}
                placeholder="Live Account"
              />
            </PanelBody>
          </SectionPanel>

          <SectionPanel>
            <PanelHeader
              eyebrow="Broker"
              title="MetaTrader 5"
              description="These credentials are encrypted per dashboard account"
              action={<Server className="h-5 w-5 text-success" />}
            />
            <PanelBody>
              <div className="grid gap-4 md:grid-cols-2">
                <Input
                  label="Login"
                  value={config.MT5_LOGIN}
                  onChange={(event) => updateField("MT5_LOGIN", event.target.value)}
                  placeholder="Account number"
                  disabled={isSubmitting}
                />
                <Input
                  label="Password"
                  type="password"
                  value={config.MT5_PASSWORD}
                  onChange={(event) => updateField("MT5_PASSWORD", event.target.value)}
                  placeholder={configuredSecrets.includes("MT5_PASSWORD") ? "Configured" : "Password"}
                  disabled={isSubmitting}
                />
                <div className="md:col-span-2">
                  <Input
                    label="Server"
                    value={config.MT5_SERVER}
                    onChange={(event) => updateField("MT5_SERVER", event.target.value)}
                    placeholder="Broker-Real"
                    disabled={isSubmitting}
                  />
                </div>
              </div>
            </PanelBody>
          </SectionPanel>

          {(error || message) && (
            <div
              className={`rounded-xl border px-4 py-3 text-sm ${
                error
                  ? "border-danger/30 bg-danger/10 text-danger"
                  : "border-success/30 bg-success/10 text-success"
              }`}
            >
              <div className="flex items-center gap-2">
                {error ? <AlertCircle className="h-4 w-4" /> : <Check className="h-4 w-4" />}
                <span>{error || message}</span>
              </div>
            </div>
          )}

          <Button type="submit" variant="accent" disabled={isSubmitting} className="w-full sm:w-auto">
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            <span>{isSubmitting ? "Testing setup" : "Save & test broker"}</span>
          </Button>
        </form>

        <div className="space-y-4">
          <SectionPanel>
            <PanelHeader eyebrow="Guide" title="Setup links" />
            <PanelBody>
              <div className="space-y-3">
                <GuideLink href="https://www.metatrader5.com/en/download" label="MetaTrader 5 terminal" />
              </div>
            </PanelBody>
          </SectionPanel>

          <SectionPanel>
            <PanelHeader eyebrow="Checklist" title="Before continuing" />
            <PanelBody>
              <div className="space-y-3 text-sm text-text-secondary">
                <ChecklistItem done label="Telegram signal source managed by platform" />
                <ChecklistItem done={Boolean(config.MT5_LOGIN.trim())} label="Broker login entered" />
                <ChecklistItem
                  done={Boolean(config.MT5_PASSWORD.trim()) || configuredSecrets.includes("MT5_PASSWORD")}
                  label="Broker password saved"
                />
                <ChecklistItem done={Boolean(config.MT5_SERVER.trim())} label="Broker server entered" />
              </div>
            </PanelBody>
          </SectionPanel>
        </div>
      </AnimatedSection>
    </PageContainer>
  );
}

function GuideLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-tertiary px-3 py-2 text-sm text-text-secondary transition-colors hover:border-accent/30 hover:text-text-primary"
    >
      <span>{label}</span>
      <ExternalLink className="h-4 w-4 text-text-muted" />
    </a>
  );
}

function ChecklistItem({ done, label }: { done: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`flex h-5 w-5 items-center justify-center rounded-full border ${
          done ? "border-success/40 bg-success/10 text-success" : "border-border-subtle text-text-muted"
        }`}
      >
        {done && <Check className="h-3 w-3" />}
      </span>
      <span>{label}</span>
    </div>
  );
}
