"use client";

import { useState, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/dashboard/metric-card";
import { PerformancePanel } from "@/components/dashboard/performance-panel";
import {
  PageHeader,
  PageLoading,
  SectionPanel,
  PanelHeader,
  PanelBody,
  EmptyState,
} from "@/components/layout";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { getAnalysisSummary, runAnalysis } from "@/lib/api";
import {
  BarChart3,
  Download,
  FileText,
  RefreshCw,
  Loader2,
  Target,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Zap,
  Calendar,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";

interface AnalysisSummaryData {
  total_signals: number;
  tp2_hit: number;
  tp1_hit: number;
  sl_hit: number;
  tp_unnumbered: number;
  win_rate: number;
  tp1_to_tp2_conversion: number;
  date_range: { start: string; end: string } | null;
  avg_time_to_tp1_minutes?: number;
  avg_time_to_tp2_minutes?: number;
}

export default function AnalysisPage() {
  const { session } = useDashboard();
  const [summary, setSummary] = useState<AnalysisSummaryData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [output, setOutput] = useState<string>("");

  // Analysis parameters
  const [total, setTotal] = useState("1000");
  const [batch, setBatch] = useState("100");
  const [delay, setDelay] = useState("2");

  const loadSummary = useCallback(async () => {
    try {
      const res = await getAnalysisSummary();
      if (res.success) {
        setSummary(res.summary);
      }
    } catch (error) {
      console.error("Failed to load analysis:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setOutput("");
    loadSummary();
  }, [loadSummary, session.activeAccountId]);

  const handleFetch = async () => {
    setIsFetching(true);
    setOutput("");

    try {
      const res = await runAnalysis("fetch", {
        total: parseInt(total, 10),
        batch: parseInt(batch, 10),
        delay: parseFloat(delay),
      });

      if (res.success) {
        setOutput(res.output || "Fetch completed successfully");
        await loadSummary();
      } else {
        setOutput(`Error: ${res.error}`);
      }
    } catch (error) {
      setOutput(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsFetching(false);
    }
  };

  const handleReport = async () => {
    setIsGenerating(true);
    setOutput("");

    try {
      const res = await runAnalysis("report");

      if (res.success) {
        setOutput(res.output || "Report generated successfully");
        await loadSummary();
      } else {
        setOutput(`Error: ${res.error}`);
      }
    } catch (error) {
      setOutput(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleFetchAndReport = async () => {
    await handleFetch();
    if (!output.startsWith("Error:")) {
      await handleReport();
    }
  };

  const formatMinutes = (minutes?: number) => {
    if (!minutes) return "-";
    if (minutes < 60) return `${minutes.toFixed(0)}m`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}h ${mins}m`;
  };

  if (isLoading) {
    return (
      <PageContainer>
        <PageLoading label="Loading analysis…" />
      </PageContainer>
    );
  }

  const isRunning = isFetching || isGenerating;

  return (
    <PageContainer>
      <AnimatedSection>
        <PageHeader
          meta="Research"
          title="Signal analysis"
          description="Fetch Telegram messages and analyze signal outcomes"
          actions={
            <Button variant="ghost" size="icon" onClick={loadSummary}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          }
        />
      </AnimatedSection>

      <AnimatedSection>
        <SectionPanel>
          <PanelHeader eyebrow="Pipeline" title="Fetch & analyze" />
          <PanelBody>
            <div className="flex flex-wrap items-end gap-4">
              <div className="w-24">
                <Input
                  label="Messages"
                  value={total}
                  onChange={(e) => setTotal(e.target.value)}
                  type="number"
                  min="1"
                />
              </div>
              <div className="w-24">
                <Input
                  label="Batch Size"
                  value={batch}
                  onChange={(e) => setBatch(e.target.value)}
                  type="number"
                  min="1"
                />
              </div>
              <div className="w-20">
                <Input
                  label="Delay (s)"
                  value={delay}
                  onChange={(e) => setDelay(e.target.value)}
                  type="number"
                  min="0"
                  step="0.5"
                />
              </div>

              <div className="flex gap-3 ml-auto">
                <Button
                  variant="secondary"
                  onClick={handleFetch}
                  disabled={isRunning}
                >
                  {isFetching ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Download className="w-4 h-4 mr-2" />
                  )}
                  Fetch
                </Button>

                <Button
                  variant="secondary"
                  onClick={handleReport}
                  disabled={isRunning}
                >
                  {isGenerating ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <FileText className="w-4 h-4 mr-2" />
                  )}
                  Report
                </Button>

                <Button
                  variant="accent"
                  onClick={handleFetchAndReport}
                  disabled={isRunning}
                >
                  {isRunning ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Zap className="w-4 h-4 mr-2" />
                  )}
                  Fetch + Report
                </Button>
              </div>
            </div>

            {/* Output */}
            {output && (
              <div className="mt-4 p-4 rounded-xl bg-[#070708] border border-border-subtle font-mono text-xs max-h-48 overflow-y-auto whitespace-pre-wrap text-text-secondary">
                {output}
              </div>
            )}
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>

      <AnimatedSection>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-sm font-semibold text-text-primary">Outcome summary</h2>
          {summary?.date_range && (
            <Badge variant="default">
              <Calendar className="w-3 h-3 mr-1" />
              {summary.date_range.start} to {summary.date_range.end}
            </Badge>
          )}
        </div>
      </AnimatedSection>

      {/* Metrics Grid */}
      {summary && summary.total_signals > 0 ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <AnimatedSection className="stagger-1">
              <MetricCard
                label="Total signals"
                value={summary.total_signals.toString()}
                icon={<BarChart3 className="w-5 h-5" />}
                accent="accent"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-2">
              <MetricCard
                label="Win rate"
                value={`${summary.win_rate.toFixed(1)}%`}
                icon={<TrendingUp className="w-5 h-5" />}
                accent="success"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-3">
              <MetricCard
                label="TP2 hit"
                value={summary.tp2_hit.toString()}
                icon={<Target className="w-5 h-5" />}
                accent="success"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-4">
              <MetricCard
                label="TP1 hit"
                value={summary.tp1_hit.toString()}
                icon={<Target className="w-5 h-5" />}
                accent="info"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-5">
              <MetricCard
                label="SL hit"
                value={summary.sl_hit.toString()}
                icon={<TrendingDown className="w-5 h-5" />}
                accent="danger"
              />
            </AnimatedSection>

            <AnimatedSection className="stagger-5">
              <MetricCard
                label="TP1→TP2"
                value={`${summary.tp1_to_tp2_conversion.toFixed(1)}%`}
                icon={<ArrowRight className="w-5 h-5" />}
                accent="warning"
              />
            </AnimatedSection>
          </div>

          {/* Time Metrics */}
          {(summary.avg_time_to_tp1_minutes || summary.avg_time_to_tp2_minutes) && (
            <AnimatedSection>
              <SectionPanel>
                <PanelHeader eyebrow="Timing" title="Average time to target" />
                <PanelBody>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
                      <p className="text-[10px] uppercase tracking-wider text-text-muted mb-1">
                        Time to TP1
                      </p>
                      <p className="text-2xl font-semibold text-info tabular-nums">
                        {formatMinutes(summary.avg_time_to_tp1_minutes)}
                      </p>
                    </div>
                    <div className="p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
                      <p className="text-[10px] uppercase tracking-wider text-text-muted mb-1">
                        Time to TP2
                      </p>
                      <p className="text-2xl font-semibold text-success tabular-nums">
                        {formatMinutes(summary.avg_time_to_tp2_minutes)}
                      </p>
                    </div>
                  </div>
                </PanelBody>
              </SectionPanel>
            </AnimatedSection>
          )}
        </>
      ) : (
        <AnimatedSection>
          <EmptyState
            icon={<BarChart3 className="w-5 h-5" />}
            title="No analysis data"
            description='Run "Fetch + Report" to analyze signal outcomes from your Telegram channel.'
            action={
              <Button variant="accent" onClick={handleFetchAndReport} disabled={isRunning}>
                {isRunning ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Zap className="w-4 h-4 mr-2" />
                )}
                Generate analysis
              </Button>
            }
          />
        </AnimatedSection>
      )}

      <AnimatedSection>
        <PerformancePanel
          title="Insights"
          bars={[
            {
              label: "TP1→TP2 conversion",
              value: summary?.tp1_to_tp2_conversion ?? 0,
              display: `${(summary?.tp1_to_tp2_conversion ?? 0).toFixed(1)}%`,
              tone: "accent",
            },
            {
              label: "Win rate",
              value: summary?.win_rate ?? 0,
              display: `${(summary?.win_rate ?? 0).toFixed(1)}%`,
              tone: (summary?.win_rate ?? 0) >= 50 ? "success" : "danger",
            },
            {
              label: "SL hits",
              value: summary?.sl_hit ?? 0,
              display: String(summary?.sl_hit ?? 0),
              tone: (summary?.sl_hit ?? 0) > 0 ? "danger" : "neutral",
            },
          ]}
        />
      </AnimatedSection>
    </PageContainer>
  );
}
