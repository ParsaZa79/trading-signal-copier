"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PnlBadge } from "./pnl-badge";
import { ModifyDialog } from "./modify-dialog";
import { SymbolCell } from "./symbol-icon";
import {
  SectionPanel,
  PanelHeader,
  PanelBody,
  EmptyState,
} from "@/components/layout";
import { formatNumber } from "@/lib/utils";
import { closePosition, modifyPosition } from "@/lib/api";
import type { Position } from "@/types";
import { Edit2, X, AlertCircle, TrendingUp, TrendingDown } from "lucide-react";

interface PositionsTableProps {
  positions: Position[];
  onRefresh?: () => void;
}

export function PositionsTable({ positions, onRefresh }: PositionsTableProps) {
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(
    null
  );
  const [isModifyOpen, setIsModifyOpen] = useState(false);
  const [isLoading, setIsLoading] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleModify = async (sl: number, tp: number) => {
    if (!selectedPosition) return;

    setIsLoading(selectedPosition.ticket);
    setError(null);

    try {
      const result = await modifyPosition(selectedPosition.ticket, sl, tp);
      if (!result.success) {
        setError(result.error || "Failed to modify position");
      } else {
        setIsModifyOpen(false);
        onRefresh?.();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to modify position");
    } finally {
      setIsLoading(null);
    }
  };

  const handleClose = async (ticket: number) => {
    if (!confirm("Are you sure you want to close this position?")) return;

    setIsLoading(ticket);
    setError(null);

    try {
      const result = await closePosition(ticket);
      if (!result.success) {
        setError(result.error || "Failed to close position");
      } else {
        onRefresh?.();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to close position");
    } finally {
      setIsLoading(null);
    }
  };

  const totalPnL = positions.reduce((sum, p) => sum + p.profit, 0);
  const isPositive = totalPnL >= 0;

  return (
    <>
      <SectionPanel>
        <PanelHeader
          eyebrow="Holdings"
          title={
            <span className="inline-flex items-center gap-2">
              Open positions
              <Badge variant="default" size="sm">
                {positions.length} active
              </Badge>
            </span>
          }
          metric={{
            label: "Unrealized P&L",
            value: `${isPositive ? "+" : ""}${formatNumber(totalPnL, 2)} USD`,
            tone: isPositive ? "success" : "danger",
          }}
          action={
            <div className="flex items-center gap-1 p-1 rounded-xl bg-bg-tertiary/80 border border-border-subtle">
              <span className="px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-elevated text-text-primary border border-border-default">
                Open
              </span>
              <Link
                href="/history"
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-text-muted hover:text-text-secondary transition-colors"
              >
                History
              </Link>
            </div>
          }
        />

        {error && (
          <div className="mx-5 sm:mx-6 mb-4 p-3 rounded-xl bg-danger/10 border border-danger/20 flex items-center gap-3">
            <AlertCircle className="w-4 h-4 text-danger shrink-0" />
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        <PanelBody flush>
          {positions.length === 0 ? (
            <EmptyState
              icon={<TrendingUp className="w-5 h-5" />}
              title="No open positions"
              description="Start trading to see your positions here"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr className="border-b border-border-subtle bg-bg-tertiary/30">
                    <th className="px-6 py-3 text-left">Symbol</th>
                    <th className="px-6 py-3 text-left">Side</th>
                    <th className="px-6 py-3 text-right">Size</th>
                    <th className="px-6 py-3 text-right">Entry</th>
                    <th className="px-6 py-3 text-right">Mark</th>
                    <th className="px-6 py-3 text-right">SL</th>
                    <th className="px-6 py-3 text-right">TP</th>
                    <th className="px-6 py-3 text-right">P&L</th>
                    <th className="px-6 py-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((position) => (
                    <tr
                      key={position.ticket}
                      className="border-b border-border-subtle last:border-0 group"
                    >
                      <td className="px-6 py-4">
                        <SymbolCell
                          symbol={position.symbol}
                          subtitle={`#${position.ticket}`}
                          size="sm"
                        />
                      </td>
                      <td className="px-6 py-4">
                        <Badge
                          variant={
                            position.type === "buy" ? "success" : "danger"
                          }
                          className="gap-1"
                        >
                          {position.type === "buy" ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : (
                            <TrendingDown className="w-3 h-3" />
                          )}
                          {position.type.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-sm text-text-primary tabular-nums font-medium">
                          {position.volume}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-sm text-text-secondary tabular-nums font-mono">
                          {formatNumber(position.price_open, 5)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-sm text-text-primary tabular-nums font-mono">
                          {position.price_current
                            ? formatNumber(position.price_current, 5)
                            : "-"}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`text-sm tabular-nums font-mono ${
                            position.sl > 0
                              ? "text-danger"
                              : "text-text-muted"
                          }`}
                        >
                          {position.sl > 0
                            ? formatNumber(position.sl, 5)
                            : "-"}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span
                          className={`text-sm tabular-nums font-mono ${
                            position.tp > 0
                              ? "text-success"
                              : "text-text-muted"
                          }`}
                        >
                          {position.tp > 0
                            ? formatNumber(position.tp, 5)
                            : "-"}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <PnlBadge value={position.profit} />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex justify-center gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => {
                              setSelectedPosition(position);
                              setIsModifyOpen(true);
                            }}
                            disabled={isLoading === position.ticket}
                            className="h-8 w-8"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            size="icon"
                            variant="danger"
                            onClick={() => handleClose(position.ticket)}
                            disabled={isLoading === position.ticket}
                            className="h-8 w-8"
                          >
                            <X className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </PanelBody>
      </SectionPanel>

      <ModifyDialog
        position={selectedPosition}
        isOpen={isModifyOpen}
        onClose={() => {
          setIsModifyOpen(false);
          setSelectedPosition(null);
        }}
        onSubmit={handleModify}
        isLoading={isLoading !== null}
      />
    </>
  );
}
