"use client";

import { cn, formatCurrency } from "@/lib/utils";
import type { AccountInfo } from "@/types";

interface AssetBreakdownProps {
  account: AccountInfo | null;
  floatingPnL: number;
  className?: string;
}

export function AssetBreakdown({
  account,
  floatingPnL,
  className,
}: AssetBreakdownProps) {
  const balance = account?.balance ?? 0;
  const margin = account?.margin ?? 0;
  const freeMargin = account?.free_margin ?? 0;
  const equity = account?.equity ?? 0;

  const segments = [
    {
      label: "Balance",
      value: balance,
      color: "bg-info",
    },
    {
      label: "Margin",
      value: margin,
      color: "bg-warning",
    },
    {
      label: "Free Margin",
      value: freeMargin,
      color: "bg-success",
    },
    {
      label: "Floating",
      value: Math.abs(floatingPnL),
      color: floatingPnL >= 0 ? "bg-accent" : "bg-danger",
    },
  ].filter((s) => s.value > 0);

  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;

  return (
    <section
      className={cn(
        "rounded-2xl border border-border-subtle bg-bg-secondary/50 p-5",
        className
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text-primary">Overview</h3>
        <span className="text-xs text-text-muted tabular-nums">
          Equity {formatCurrency(equity)}
        </span>
      </div>

      <div className="h-2.5 rounded-full overflow-hidden flex bg-bg-tertiary mb-4">
        {segments.map((segment) => (
          <div
            key={segment.label}
            className={cn("h-full transition-all", segment.color)}
            style={{ width: `${(segment.value / total) * 100}%` }}
            title={`${segment.label}: ${formatCurrency(segment.value)}`}
          />
        ))}
      </div>

      <ul className="space-y-3">
        {segments.map((segment) => (
          <li
            key={segment.label}
            className="flex items-center justify-between text-sm"
          >
            <div className="flex items-center gap-2">
              <span className={cn("w-2 h-2 rounded-full", segment.color)} />
              <span className="text-text-secondary">{segment.label}</span>
            </div>
            <span className="font-medium text-text-primary tabular-nums">
              {formatCurrency(segment.value)}
            </span>
          </li>
        ))}
      </ul>

      {account?.margin && account.margin > 0 && (
        <div className="mt-4 pt-4 border-t border-border-subtle">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-text-muted">Margin level</span>
            <span
              className={cn(
                "font-semibold tabular-nums",
                (equity / account.margin) * 100 > 200
                  ? "text-success"
                  : "text-warning"
              )}
            >
              {((equity / account.margin) * 100).toFixed(0)}%
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-success to-accent transition-all"
              style={{
                width: `${Math.min(100, (equity / account.margin) * 50)}%`,
              }}
            />
          </div>
        </div>
      )}
    </section>
  );
}
