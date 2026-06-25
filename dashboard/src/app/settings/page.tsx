"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import {
  PageHeader,
  SectionPanel,
  PanelHeader,
  PanelBody,
  PageLoading,
} from "@/components/layout";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { MetricCard } from "@/components/dashboard/metric-card";
import { getHealth } from "@/lib/api";
import type { HealthStatus } from "@/types";
import {
  Server,
  Wifi,
  Shield,
  CheckCircle,
  XCircle,
  Zap,
  Activity,
  DollarSign,
  Sparkles,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";
import { formatCurrency } from "@/lib/utils";

export default function SettingsPage() {
  const { session } = useDashboard();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchHealth = async () => {
    try {
      const result = await getHealth();
      setHealth(result);
    } catch (error) {
      console.error("Failed to fetch health:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setIsLoading(true);
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, [session.activeAccountId]);

  return (
    <PageContainer>
      <AnimatedSection>
        <PageHeader
          meta="System"
          title="Settings"
          description="Connection health and application info"
        />
      </AnimatedSection>

      <AnimatedSection>
        <SectionPanel>
          <PanelHeader eyebrow="Infrastructure" title="Connection status" />
          <PanelBody>
            {isLoading ? (
              <PageLoading label="Checking connection status…" className="min-h-[200px]" />
            ) : !health ? (
              <div className="flex items-center gap-3 p-4 rounded-xl bg-danger/10 border border-danger/20">
                <XCircle className="w-5 h-5 text-danger" />
                <span className="text-sm text-danger">
                  Unable to connect to API server
                </span>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-bg-elevated border border-border-default flex items-center justify-center">
                      <Wifi className="w-5 h-5 text-success" />
                    </div>
                    <div>
                      <p className="font-medium text-text-primary">API server</p>
                      <p className="text-xs text-text-muted">Main backend connection</p>
                    </div>
                  </div>
                  <Badge variant="success">{health.status.toUpperCase()}</Badge>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <StatusRow
                    icon={<Activity className="w-4 h-4" />}
                    label="MT5 connected"
                    status={health.mt5.connected}
                  />
                  {health.mt5.ping_ok !== undefined && (
                    <StatusRow
                      icon={<Zap className="w-4 h-4" />}
                      label="Ping OK"
                      status={health.mt5.ping_ok}
                    />
                  )}
                  {health.mt5.account_accessible !== undefined && (
                    <StatusRow
                      icon={<Shield className="w-4 h-4" />}
                      label="Account accessible"
                      status={health.mt5.account_accessible}
                    />
                  )}
                  {health.mt5.trading_enabled !== undefined && (
                    <StatusRow
                      icon={<CheckCircle className="w-4 h-4" />}
                      label="Trading enabled"
                      status={health.mt5.trading_enabled}
                    />
                  )}
                </div>

                {health.mt5.account_balance !== undefined && (
                  <div className="p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <DollarSign className="w-5 h-5 text-text-secondary" />
                      <span className="text-sm text-text-secondary">
                        Account balance
                      </span>
                    </div>
                    <span className="text-xl font-semibold text-text-primary tabular-nums">
                      {formatCurrency(health.mt5.account_balance)}
                    </span>
                  </div>
                )}

                {health.mt5.error && (
                  <div className="p-4 rounded-xl bg-danger/10 border border-danger/20">
                    <p className="text-sm font-medium text-danger mb-1">Error</p>
                    <p className="text-xs text-danger/80">{health.mt5.error}</p>
                  </div>
                )}
              </div>
            )}
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Dashboard" value="v0.1.0" icon={<Sparkles className="w-5 h-5" />} accent="accent" />
        <MetricCard label="API" value="v0.1.0" icon={<Server className="w-5 h-5" />} accent="success" />
        <MetricCard label="Next.js" value="16.1.1" icon={<Sparkles className="w-5 h-5" />} accent="info" />
        <MetricCard label="React" value="19.2.3" icon={<Sparkles className="w-5 h-5" />} accent="warning" />
      </AnimatedSection>
    </PageContainer>
  );
}

function StatusRow({
  icon,
  label,
  status,
}: {
  icon: React.ReactNode;
  label: string;
  status: boolean;
}) {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
      <div className="flex items-center gap-3">
        <span className="text-text-muted">{icon}</span>
        <span className="text-sm text-text-primary">{label}</span>
      </div>
      {status ? (
        <CheckCircle className="w-4 h-4 text-success" />
      ) : (
        <XCircle className="w-4 h-4 text-danger" />
      )}
    </div>
  );
}
