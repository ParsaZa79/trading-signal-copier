"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ClipboardList,
  Network,
  Play,
  Plus,
  RefreshCw,
  Repeat2,
  Shield,
  Zap,
} from "lucide-react";
import { PageHeader, SectionPanel, PanelHeader, PanelBody, EmptyState } from "@/components/layout";
import { PageContainer, AnimatedSection } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  createPlatformProvider,
  createPlatformSubscription,
  createPlatformTradeEvent,
  getPlatformOverview,
  processPlatformTradeEvent,
  runPlatformStressTest,
  savePlatformRiskPolicy,
} from "@/lib/api";
import type {
  PlatformCopyMode,
  PlatformOverview,
  PlatformProvider,
  PlatformTradeSide,
} from "@/types";

const emptyOverview: PlatformOverview = {
  providers: [],
  subscriptions: [],
  risk_policy: {
    user_id: "",
    paper_trading: true,
    require_stop_loss: true,
    allowed_symbols: [],
    max_daily_loss: null,
    max_open_trades: 100,
    default_fixed_lot: 0.01,
  },
  recent_events: [],
  recent_executions: [],
  metrics: {
    provider_count: 0,
    available_provider_count: 0,
    subscription_count: 0,
    paper_execution_count: 0,
    blocked_execution_count: 0,
  },
};

function parseNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseTakeProfits(value: string): number[] {
  return value
    .split(",")
    .map((part) => Number(part.trim()))
    .filter((part) => Number.isFinite(part));
}

function formatDate(value?: string) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function MetricCard({
  title,
  value,
  icon,
  tone = "neutral",
}: {
  title: string;
  value: string | number;
  icon: ReactNode;
  tone?: "neutral" | "success" | "danger" | "accent";
}) {
  const toneClass =
    tone === "success"
      ? "text-success bg-success/10 border-success/20"
      : tone === "danger"
        ? "text-danger bg-danger/10 border-danger/20"
        : tone === "accent"
          ? "text-accent bg-accent/10 border-accent/20"
          : "text-text-secondary bg-bg-tertiary border-border-subtle";
  return (
    <div className="rounded-2xl border border-border-subtle bg-bg-secondary p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-muted">{title}</p>
          <p className="mt-2 text-2xl font-semibold text-text-primary tabular-nums">{value}</p>
        </div>
        <div className={`w-10 h-10 rounded-xl border flex items-center justify-center ${toneClass}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

export default function PlatformPage() {
  const [overview, setOverview] = useState<PlatformOverview>(emptyOverview);
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [stressResult, setStressResult] = useState<string | null>(null);

  const [providerName, setProviderName] = useState("Gold Desk");
  const [providerSource, setProviderSource] = useState("manual");
  const [providerDescription, setProviderDescription] = useState("Manual dashboard trades and signal events");

  const [allowedSymbols, setAllowedSymbols] = useState("XAUUSD, EURUSD, GBPUSD");
  const [maxDailyLoss, setMaxDailyLoss] = useState("200");
  const [maxOpenTrades, setMaxOpenTrades] = useState("100");
  const [requireStopLoss, setRequireStopLoss] = useState(true);

  const [subscriptionProviderId, setSubscriptionProviderId] = useState("");
  const [copyMode, setCopyMode] = useState<PlatformCopyMode>("fixed_lot");
  const [fixedLot, setFixedLot] = useState("0.02");
  const [multiplier, setMultiplier] = useState("1");

  const [eventProviderId, setEventProviderId] = useState("");
  const [symbol, setSymbol] = useState("XAUUSD");
  const [side, setSide] = useState<PlatformTradeSide>("buy");
  const [entryPrice, setEntryPrice] = useState("2350");
  const [stopLoss, setStopLoss] = useState("2340");
  const [takeProfits, setTakeProfits] = useState("2360, 2370");
  const [eventVolume, setEventVolume] = useState("0.01");
  const [stressCount, setStressCount] = useState("50");

  const providerOptions = useMemo(
    () =>
      overview.providers.map((provider: PlatformProvider) => ({
        value: provider.id,
        label: `${provider.name} (${provider.source_type})`,
      })),
    [overview.providers]
  );

  const loadOverview = useCallback(async () => {
    setError(null);
    try {
      const next = await getPlatformOverview();
      setOverview(next);
      const firstProviderId = next.providers[0]?.id ?? "";
      setSubscriptionProviderId((current) => current || firstProviderId);
      setEventProviderId((current) => current || firstProviderId);
      setAllowedSymbols(next.risk_policy.allowed_symbols.join(", "));
      setMaxDailyLoss(next.risk_policy.max_daily_loss?.toString() ?? "");
      setMaxOpenTrades(next.risk_policy.max_open_trades.toString());
      setRequireStopLoss(next.risk_policy.require_stop_loss);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load platform");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  async function runAction(label: string, action: () => Promise<void>) {
    setIsBusy(true);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(label);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setIsBusy(false);
    }
  }

  const activeEventProviderId = eventProviderId || providerOptions[0]?.value || "";

  return (
    <PageContainer>
      <AnimatedSection>
        <PageHeader
          meta="Paper-first automation"
          title="Trading platform"
          description="Create providers, configure risk, copy trades, submit manual events, and stress-test the paper execution layer. No live-money execution happens here."
        />
      </AnimatedSection>

      {(error || message) && (
        <AnimatedSection>
          <div
            className={`rounded-2xl border p-4 text-sm ${
              error
                ? "border-danger/20 bg-danger/10 text-danger"
                : "border-success/20 bg-success/10 text-success"
            }`}
          >
            {error || message}
          </div>
        </AnimatedSection>
      )}

      <AnimatedSection className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
        <MetricCard title="Owned providers" value={overview.metrics.provider_count} icon={<Network className="w-5 h-5" />} tone="accent" />
        <MetricCard title="Available" value={overview.metrics.available_provider_count} icon={<ClipboardList className="w-5 h-5" />} />
        <MetricCard title="Subscriptions" value={overview.metrics.subscription_count} icon={<Repeat2 className="w-5 h-5" />} />
        <MetricCard title="Paper executions" value={overview.metrics.paper_execution_count} icon={<CheckCircle2 className="w-5 h-5" />} tone="success" />
        <MetricCard title="Blocked" value={overview.metrics.blocked_execution_count} icon={<AlertTriangle className="w-5 h-5" />} tone="danger" />
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <SectionPanel>
          <PanelHeader eyebrow="Source" title="Create provider" />
          <PanelBody className="space-y-4">
            <Input label="Provider name" value={providerName} onChange={(event) => setProviderName(event.target.value)} />
            <Select
              label="Source type"
              value={providerSource}
              onChange={(event) => setProviderSource(event.target.value)}
              options={[
                { value: "manual", label: "Manual dashboard" },
                { value: "telegram", label: "Telegram signal channel" },
                { value: "webhook", label: "Webhook / API" },
                { value: "mt5_mirror", label: "MT5 mirror" },
              ]}
            />
            <Textarea
              label="Description"
              value={providerDescription}
              onChange={(event) => setProviderDescription(event.target.value)}
              rows={3}
            />
            <Button
              disabled={isBusy || !providerName.trim()}
              onClick={() =>
                runAction("Provider created", async () => {
                  const response = await createPlatformProvider({
                    name: providerName,
                    source_type: providerSource,
                    description: providerDescription,
                    visibility: "public",
                  });
                  setSubscriptionProviderId(response.provider.id);
                  setEventProviderId(response.provider.id);
                })
              }
            >
              <Plus className="w-4 h-4" /> Create provider
            </Button>
          </PanelBody>
        </SectionPanel>

        <SectionPanel>
          <PanelHeader eyebrow="Safety" title="Risk policy" />
          <PanelBody className="space-y-4">
            <Input label="Allowed symbols" value={allowedSymbols} onChange={(event) => setAllowedSymbols(event.target.value)} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Max daily loss" value={maxDailyLoss} onChange={(event) => setMaxDailyLoss(event.target.value)} />
              <Input label="Max open trades" value={maxOpenTrades} onChange={(event) => setMaxOpenTrades(event.target.value)} />
            </div>
            <label className="flex items-center gap-3 rounded-xl border border-border-subtle bg-bg-tertiary px-4 py-3 text-sm text-text-secondary">
              <input
                type="checkbox"
                checked={requireStopLoss}
                onChange={(event) => setRequireStopLoss(event.target.checked)}
              />
              Require stop loss before copying
            </label>
            <Button
              disabled={isBusy}
              onClick={() =>
                runAction("Risk policy saved", async () => {
                  await savePlatformRiskPolicy({
                    paper_trading: true,
                    require_stop_loss: requireStopLoss,
                    allowed_symbols: allowedSymbols
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean),
                    max_daily_loss: parseNumber(maxDailyLoss) ?? null,
                    max_open_trades: parseNumber(maxOpenTrades) ?? 100,
                  });
                })
              }
            >
              <Shield className="w-4 h-4" /> Save risk policy
            </Button>
          </PanelBody>
        </SectionPanel>

        <SectionPanel>
          <PanelHeader eyebrow="Follower" title="Copy subscription" />
          <PanelBody className="space-y-4">
            <Select
              label="Provider"
              value={subscriptionProviderId}
              onChange={(event) => setSubscriptionProviderId(event.target.value)}
              options={providerOptions}
              placeholder={providerOptions.length ? undefined : "Create a provider first"}
              disabled={!providerOptions.length}
            />
            <Select
              label="Copy mode"
              value={copyMode}
              onChange={(event) => setCopyMode(event.target.value as PlatformCopyMode)}
              options={[
                { value: "fixed_lot", label: "Fixed lot" },
                { value: "multiplier", label: "Multiplier" },
                { value: "mirror", label: "Mirror event volume" },
              ]}
            />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Fixed lot" value={fixedLot} onChange={(event) => setFixedLot(event.target.value)} />
              <Input label="Multiplier" value={multiplier} onChange={(event) => setMultiplier(event.target.value)} />
            </div>
            <Button
              disabled={isBusy || !subscriptionProviderId}
              onClick={() =>
                runAction("Copy subscription saved", async () => {
                  await createPlatformSubscription({
                    provider_id: subscriptionProviderId,
                    copy_mode: copyMode,
                    fixed_lot: parseNumber(fixedLot),
                    multiplier: parseNumber(multiplier),
                    paper_trading: true,
                  });
                })
              }
            >
              <Repeat2 className="w-4 h-4" /> Subscribe in paper mode
            </Button>
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <SectionPanel>
          <PanelHeader eyebrow="Trade intent" title="Manual event → paper copy" />
          <PanelBody className="space-y-4">
            <Select
              label="Provider"
              value={activeEventProviderId}
              onChange={(event) => setEventProviderId(event.target.value)}
              options={providerOptions}
              disabled={!providerOptions.length}
            />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Symbol" value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} />
              <Select
                label="Side"
                value={side}
                onChange={(event) => setSide(event.target.value as PlatformTradeSide)}
                options={[
                  { value: "buy", label: "Buy" },
                  { value: "sell", label: "Sell" },
                ]}
              />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Input label="Entry" value={entryPrice} onChange={(event) => setEntryPrice(event.target.value)} />
              <Input label="Stop loss" value={stopLoss} onChange={(event) => setStopLoss(event.target.value)} />
              <Input label="Take profits" value={takeProfits} onChange={(event) => setTakeProfits(event.target.value)} />
              <Input label="Event volume" value={eventVolume} onChange={(event) => setEventVolume(event.target.value)} />
            </div>
            <Button
              disabled={isBusy || !activeEventProviderId}
              onClick={() =>
                runAction("Manual trade event processed", async () => {
                  const response = await createPlatformTradeEvent({
                    provider_id: activeEventProviderId,
                    action: "open",
                    symbol,
                    side,
                    entry_price: parseNumber(entryPrice),
                    stop_loss: parseNumber(stopLoss),
                    take_profits: parseTakeProfits(takeProfits),
                    volume: parseNumber(eventVolume),
                    source: "manual_dashboard",
                  });
                  await processPlatformTradeEvent(response.event.id);
                })
              }
            >
              <Play className="w-4 h-4" /> Create & process paper event
            </Button>
          </PanelBody>
        </SectionPanel>

        <SectionPanel>
          <PanelHeader eyebrow="Load test" title="Paper stress test" />
          <PanelBody className="space-y-4">
            <p className="text-sm text-text-secondary leading-relaxed">
              Generates a burst of normalized XAUUSD events, routes them through the copy/risk engine, and creates paper executions only.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Event count" value={stressCount} onChange={(event) => setStressCount(event.target.value)} />
              <Select label="Provider" value={activeEventProviderId} onChange={(event) => setEventProviderId(event.target.value)} options={providerOptions} disabled={!providerOptions.length} />
            </div>
            <Button
              disabled={isBusy || !activeEventProviderId}
              onClick={() =>
                runAction("Stress test completed", async () => {
                  const response = await runPlatformStressTest({
                    provider_id: activeEventProviderId,
                    count: parseNumber(stressCount) ?? 50,
                  });
                  setStressResult(
                    `${response.result.events} events → ${response.result.executions_created} accepted, ${response.result.blocked} blocked in ${response.result.duration_ms}ms`
                  );
                })
              }
            >
              <Zap className="w-4 h-4" /> Run stress test
            </Button>
            {stressResult && (
              <div className="rounded-xl border border-border-subtle bg-bg-tertiary p-3 text-sm text-text-secondary">
                {stressResult}
              </div>
            )}
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <SectionPanel>
          <PanelHeader
            eyebrow="Activity"
            title="Recent trade events"
            action={
              <Button variant="ghost" size="sm" onClick={loadOverview} disabled={isLoading}>
                <RefreshCw className="w-4 h-4" /> Refresh
              </Button>
            }
          />
          <PanelBody flush>
            {isLoading ? (
              <EmptyState icon={<Activity className="w-5 h-5 animate-pulse" />} title="Loading platform…" />
            ) : overview.recent_events.length === 0 ? (
              <EmptyState icon={<Bot className="w-5 h-5" />} title="No events yet" description="Create a provider and manual event to start." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full data-table">
                  <thead>
                    <tr>
                      <th className="px-4 py-3 text-left">Provider</th>
                      <th className="px-4 py-3 text-left">Event</th>
                      <th className="px-4 py-3 text-left">Status</th>
                      <th className="px-4 py-3 text-left">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.recent_events.map((event) => (
                      <tr key={event.id} className="border-t border-border-subtle">
                        <td className="px-4 py-3 text-sm text-text-secondary">{event.provider_name}</td>
                        <td className="px-4 py-3 text-sm text-text-primary">
                          {event.action} {event.side} {event.symbol}
                        </td>
                        <td className="px-4 py-3 text-sm text-text-secondary">{event.status}</td>
                        <td className="px-4 py-3 text-xs text-text-muted">{formatDate(event.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </PanelBody>
        </SectionPanel>

        <SectionPanel>
          <PanelHeader eyebrow="Paper ledger" title="Recent executions" />
          <PanelBody flush>
            {overview.recent_executions.length === 0 ? (
              <EmptyState icon={<ClipboardList className="w-5 h-5" />} title="No paper executions yet" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full data-table">
                  <thead>
                    <tr>
                      <th className="px-4 py-3 text-left">Provider</th>
                      <th className="px-4 py-3 text-left">Trade</th>
                      <th className="px-4 py-3 text-right">Lot</th>
                      <th className="px-4 py-3 text-left">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.recent_executions.map((execution) => (
                      <tr key={execution.id} className="border-t border-border-subtle">
                        <td className="px-4 py-3 text-sm text-text-secondary">{execution.provider_name}</td>
                        <td className="px-4 py-3 text-sm text-text-primary">
                          {execution.side} {execution.symbol}
                        </td>
                        <td className="px-4 py-3 text-right text-sm tabular-nums">{execution.volume}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={execution.status === "accepted" ? "text-success" : "text-danger"}>
                            {execution.status}{execution.blocked_reason ? ` · ${execution.blocked_reason}` : ""}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>
    </PageContainer>
  );
}
