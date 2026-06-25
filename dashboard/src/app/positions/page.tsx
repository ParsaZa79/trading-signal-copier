"use client";

import { useDashboard } from "@/components/layout/dashboard-layout";
import { PositionsTable } from "@/components/dashboard/positions-table";
import { MetricCard } from "@/components/dashboard/metric-card";
import {
  PageHeader,
  SectionPanel,
  PanelHeader,
  PanelBody,
  EmptyState,
} from "@/components/layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getPendingOrders, cancelOrder } from "@/lib/api";
import type { PendingOrder } from "@/types";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  X,
  RefreshCw,
  Clock,
  TrendingUp,
  TrendingDown,
  Activity,
} from "lucide-react";
import { SymbolCell } from "@/components/dashboard/symbol-icon";
import { PageContainer, AnimatedSection } from "@/components/motion";

export default function PositionsPage() {
  const { positions, reconnect, session } = useDashboard();
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([]);
  const [isLoadingPending, setIsLoadingPending] = useState(true);

  const floatingPnL = useMemo(
    () => positions.reduce((sum, p) => sum + p.profit, 0),
    [positions]
  );

  const fetchPendingOrders = useCallback(async () => {
    try {
      const orders = await getPendingOrders();
      setPendingOrders(orders);
    } catch (error) {
      console.error("Failed to fetch pending orders:", error);
    } finally {
      setIsLoadingPending(false);
    }
  }, []);

  useEffect(() => {
    setIsLoadingPending(true);
    setPendingOrders([]);
    fetchPendingOrders();
    const interval = setInterval(fetchPendingOrders, 5000);
    return () => clearInterval(interval);
  }, [fetchPendingOrders, session.activeAccountId]);

  const handleCancelOrder = async (ticket: number) => {
    if (!confirm("Are you sure you want to cancel this order?")) return;
    try {
      await cancelOrder(ticket);
      fetchPendingOrders();
    } catch (error) {
      console.error("Failed to cancel order:", error);
    }
  };

  return (
    <PageContainer>
      <AnimatedSection>
        <PageHeader
          meta="Trading"
          title="Positions"
          description="Open positions and pending orders"
          actions={
            <Button variant="outline" onClick={reconnect}>
              <RefreshCw className="w-4 h-4" />
              Refresh
            </Button>
          }
        />
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          label="Open positions"
          value={String(positions.length)}
          icon={<Activity className="w-5 h-5" />}
          accent="info"
        />
        <MetricCard
          label="Pending orders"
          value={String(pendingOrders.length)}
          icon={<Clock className="w-5 h-5" />}
          accent="warning"
        />
        <MetricCard
          label="Floating P&L"
          value={`${floatingPnL >= 0 ? "+" : ""}$${Math.abs(floatingPnL).toFixed(2)}`}
          icon={
            floatingPnL >= 0 ? (
              <TrendingUp className="w-5 h-5" />
            ) : (
              <TrendingDown className="w-5 h-5" />
            )
          }
          accent={floatingPnL >= 0 ? "success" : "danger"}
        />
      </AnimatedSection>

      <AnimatedSection>
        <PositionsTable positions={positions} onRefresh={reconnect} />
      </AnimatedSection>

      <AnimatedSection>
        <SectionPanel>
          <PanelHeader
            eyebrow="Orders"
            title={
              <span className="inline-flex items-center gap-2">
                Pending orders
                <Badge variant="default" size="sm">
                  {pendingOrders.length}
                </Badge>
              </span>
            }
          />
          <PanelBody flush>
            {isLoadingPending ? (
              <EmptyState
                compact
                icon={<Clock className="w-5 h-5 animate-pulse" />}
                title="Loading pending orders"
              />
            ) : pendingOrders.length === 0 ? (
              <EmptyState
                icon={<Clock className="w-5 h-5" />}
                title="No pending orders"
                description="Create a limit or stop order to see it here"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full data-table">
                  <thead>
                    <tr className="border-b border-border-subtle bg-bg-tertiary/30">
                      <th className="px-6 py-3 text-left">Symbol</th>
                      <th className="px-6 py-3 text-left">Type</th>
                      <th className="px-6 py-3 text-right">Size</th>
                      <th className="px-6 py-3 text-right">Price</th>
                      <th className="px-6 py-3 text-right">SL</th>
                      <th className="px-6 py-3 text-right">TP</th>
                      <th className="px-6 py-3 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingOrders.map((order) => (
                      <tr
                        key={order.ticket}
                        className="border-b border-border-subtle last:border-0 group"
                      >
                        <td className="px-6 py-4">
                          <SymbolCell symbol={order.symbol} size="sm" />
                        </td>
                        <td className="px-6 py-4">
                          <Badge
                            variant={
                              order.type.includes("buy") ? "info" : "warning"
                            }
                            className="gap-1"
                          >
                            {order.type.includes("buy") ? (
                              <TrendingUp className="w-3 h-3" />
                            ) : (
                              <TrendingDown className="w-3 h-3" />
                            )}
                            {order.type.replace("_", " ").toUpperCase()}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 text-right tabular-nums text-sm">
                          {order.volume}
                        </td>
                        <td className="px-6 py-4 text-right tabular-nums font-mono text-sm text-text-secondary">
                          {order.price_open.toFixed(5)}
                        </td>
                        <td className="px-6 py-4 text-right tabular-nums font-mono text-sm text-danger">
                          {order.sl > 0 ? order.sl.toFixed(5) : "-"}
                        </td>
                        <td className="px-6 py-4 text-right tabular-nums font-mono text-sm text-success">
                          {order.tp > 0 ? order.tp.toFixed(5) : "-"}
                        </td>
                        <td className="px-6 py-4 text-center">
                          <Button
                            size="icon"
                            variant="danger"
                            onClick={() => handleCancelOrder(order.ticket)}
                            className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <X className="w-3.5 h-3.5" />
                          </Button>
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
