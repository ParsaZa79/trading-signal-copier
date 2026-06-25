"use client";

import { useState, useEffect } from "react";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { PortfolioHero } from "@/components/dashboard/portfolio-hero";
import { MetricCard } from "@/components/dashboard/metric-card";
import { AssetBreakdown } from "@/components/dashboard/asset-breakdown";
import { PerformancePanel } from "@/components/dashboard/performance-panel";
import { PositionsSummary } from "@/components/dashboard/positions-summary";
import { PositionsTable } from "@/components/dashboard/positions-table";
import { formatCurrency } from "@/lib/utils";
import { getTradeHistory } from "@/lib/api";
import type { TradeHistoryEntry } from "@/types";
import {
  Activity,
  BarChart3,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";

function getTodayDateRange() {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  return {
    from: today.toISOString().split("T")[0],
    to: tomorrow.toISOString().split("T")[0],
  };
}

export default function DashboardPage() {
  const { positions, account, session } = useDashboard();
  const [todayTrades, setTodayTrades] = useState<TradeHistoryEntry[]>([]);
  const [isLoadingTrades, setIsLoadingTrades] = useState(true);
  const hasAccountConnection = account !== null;

  useEffect(() => {
    const fetchTodayTrades = async () => {
      if (!hasAccountConnection) {
        setTodayTrades([]);
        setIsLoadingTrades(false);
        return;
      }

      setIsLoadingTrades(true);
      try {
        const { from, to } = getTodayDateRange();
        const result = await getTradeHistory(1, 100, undefined, from, to);
        setTodayTrades(result.trades);
      } catch (error) {
        console.error("Failed to fetch today's trades:", error);
      } finally {
        setIsLoadingTrades(false);
      }
    };

    fetchTodayTrades();
    const interval = setInterval(fetchTodayTrades, 30000);
    return () => clearInterval(interval);
  }, [hasAccountConnection, session.activeAccountId]);

  const floatingPnL = positions.reduce((sum, pos) => sum + pos.profit, 0);
  const winningPositions = positions.filter((pos) => pos.profit > 0).length;
  const losingPositions = positions.filter((pos) => pos.profit < 0).length;
  const positionsWinRate =
    positions.length > 0
      ? (winningPositions / positions.length) * 100
      : 0;

  const todayPnL = todayTrades.reduce((sum, t) => sum + t.profit, 0);
  const todayWinRate =
    todayTrades.length > 0
      ? (todayTrades.filter((t) => t.profit > 0).length / todayTrades.length) *
        100
      : 0;

  return (
    <PageContainer>
      <AnimatedSection>
        <PortfolioHero
          account={account}
          floatingPnL={floatingPnL}
          accountId={session.activeAccountId}
        />
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard
          label="Open Positions"
          value={String(positions.length)}
          sublabel={`${winningPositions} winning · ${losingPositions} losing`}
          icon={<Activity className="w-5 h-5 text-info" />}
          accent="info"
        />
        <MetricCard
          label="Floating P&L"
          value={`${floatingPnL >= 0 ? "+" : ""}${formatCurrency(floatingPnL)}`}
          sublabel={
            account?.balance
              ? `${((floatingPnL / account.balance) * 100).toFixed(2)}% of balance`
              : undefined
          }
          icon={
            floatingPnL >= 0 ? (
              <TrendingUp className="w-5 h-5 text-success" />
            ) : (
              <TrendingDown className="w-5 h-5 text-danger" />
            )
          }
          accent={floatingPnL >= 0 ? "success" : "danger"}
        />
        <MetricCard
          label="Today's Closed P&L"
          value={
            isLoadingTrades
              ? "—"
              : `${todayPnL >= 0 ? "+" : ""}${formatCurrency(todayPnL)}`
          }
          sublabel={`${todayTrades.length} trade${todayTrades.length !== 1 ? "s" : ""} closed`}
          icon={<BarChart3 className="w-5 h-5 text-accent" />}
          accent={todayPnL >= 0 ? "success" : "danger"}
        />
        <MetricCard
          label="Win Rate"
          value={`${positions.length > 0 ? positionsWinRate.toFixed(0) : todayWinRate.toFixed(0)}%`}
          sublabel={
            positions.length > 0
              ? "Open positions"
              : todayTrades.length > 0
                ? "Today's closed trades"
                : "No activity yet"
          }
          icon={<Target className="w-5 h-5 text-warning" />}
          accent="warning"
        />
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 space-y-4">
          <PositionsTable positions={positions} />
        </div>
        <div className="space-y-4">
          <AssetBreakdown account={account} floatingPnL={floatingPnL} />
          <PerformancePanel
            bars={[
              {
                label: "Open win rate",
                value: positionsWinRate,
                display: `${positionsWinRate.toFixed(0)}%`,
                tone:
                  positionsWinRate >= 50
                    ? "success"
                    : positionsWinRate > 0
                      ? "danger"
                      : "neutral",
              },
              {
                label: "Today's win rate",
                value: todayWinRate,
                display: `${todayWinRate.toFixed(0)}%`,
                tone:
                  todayWinRate >= 50
                    ? "success"
                    : todayWinRate > 0
                      ? "danger"
                      : "neutral",
              },
              {
                label: "Winning positions",
                value: winningPositions,
                display: String(winningPositions),
                tone: "success",
              },
              {
                label: "Losing positions",
                value: losingPositions,
                display: String(losingPositions),
                tone: losingPositions > 0 ? "danger" : "neutral",
              },
            ]}
          />
          <PositionsSummary positions={positions} />
        </div>
      </AnimatedSection>
    </PageContainer>
  );
}
