"use client";

import Link from "next/link";
import { SymbolIcon } from "./symbol-icon";
import { cn, formatCurrency } from "@/lib/utils";
import type { Position } from "@/types";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

interface PositionsSummaryProps {
  positions: Position[];
  className?: string;
}

export function PositionsSummary({
  positions,
  className,
}: PositionsSummaryProps) {
  const sorted = [...positions]
    .sort((a, b) => Math.abs(b.profit) - Math.abs(a.profit))
    .slice(0, 5);

  return (
    <section
      className={cn(
        "rounded-2xl border border-border-subtle bg-bg-secondary/50 p-5",
        className
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text-primary">Top Holdings</h3>
        <Link
          href="/positions"
          className="text-xs text-accent hover:text-accent-light transition-colors"
        >
          View all
        </Link>
      </div>

      {sorted.length === 0 ? (
        <p className="text-sm text-text-muted py-6 text-center">
          No open positions
        </p>
      ) : (
        <ul className="space-y-2">
          {sorted.map((position) => {
            const positive = position.profit >= 0;
            return (
              <li
                key={position.ticket}
                className="flex items-center justify-between py-2.5 px-3 rounded-xl hover:bg-bg-tertiary/60 transition-colors group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <SymbolIcon symbol={position.symbol} size="md" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {position.symbol}
                    </p>
                    <p className="text-[10px] text-text-muted uppercase">
                      {position.type} · {position.volume} lots
                    </p>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <p
                    className={cn(
                      "text-sm font-semibold tabular-nums flex items-center justify-end gap-0.5",
                      positive ? "text-success" : "text-danger"
                    )}
                  >
                    {positive ? (
                      <ArrowUpRight className="w-3 h-3" />
                    ) : (
                      <ArrowDownRight className="w-3 h-3" />
                    )}
                    {formatCurrency(position.profit)}
                  </p>
                  <p className="text-[10px] text-text-muted tabular-nums">
                    #{position.ticket}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
