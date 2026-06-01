"use client";

import { GlassCard } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";
import type { AccountInfo } from "@/types";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

interface AccountCardProps {
  account: AccountInfo | null;
}

export function AccountCard({ account }: AccountCardProps) {
  if (!account) {
    return (
      <GlassCard className="animate-pulse">
        <div className="space-y-3">
          <div className="w-20 h-3 rounded bg-bg-tertiary" />
          <div className="w-36 h-8 rounded bg-bg-tertiary" />
          <div className="w-full h-4 rounded bg-bg-tertiary" />
        </div>
      </GlassCard>
    );
  }

  const profitPercent =
    account.balance > 0 ? (account.profit / account.balance) * 100 : 0;
  const isPositive = account.profit >= 0;

  return (
    <GlassCard>
      <div className="flex items-start justify-between mb-4">
        <div className="w-10 h-10 rounded-xl bg-bg-tertiary border border-border-subtle flex items-center justify-center">
          <Wallet className="w-5 h-5 text-text-secondary" />
        </div>
        <span
          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold tabular-nums border ${
            isPositive
              ? "bg-success/10 text-success border-success/20"
              : "bg-danger/10 text-danger border-danger/20"
          }`}
        >
          {isPositive ? (
            <ArrowUpRight className="w-3 h-3" />
          ) : (
            <ArrowDownRight className="w-3 h-3" />
          )}
          {isPositive ? "+" : ""}
          {profitPercent.toFixed(2)}%
        </span>
      </div>

      <p className="text-xs text-text-muted mb-1">Account balance</p>
      <p className="text-2xl font-semibold text-text-primary tabular-nums tracking-tight">
        {formatCurrency(account.balance)}
      </p>

      <div className="mt-4 pt-4 border-t border-border-subtle flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isPositive ? (
            <TrendingUp className="w-4 h-4 text-success" />
          ) : (
            <TrendingDown className="w-4 h-4 text-danger" />
          )}
          <span
            className={`text-sm font-semibold tabular-nums ${
              isPositive ? "text-success" : "text-danger"
            }`}
          >
            {isPositive ? "+" : ""}
            {formatCurrency(account.profit)}
          </span>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-text-muted">
          P&L
        </span>
      </div>
    </GlassCard>
  );
}
