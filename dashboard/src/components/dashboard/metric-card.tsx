"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string;
  sublabel?: string;
  icon?: ReactNode;
  trend?: { value: string; positive: boolean };
  className?: string;
  accent?: "default" | "success" | "danger" | "info" | "warning" | "accent";
}

const iconTone = {
  default: "text-text-secondary",
  success: "text-success",
  danger: "text-danger",
  info: "text-info",
  warning: "text-warning",
  accent: "text-accent",
};

export function MetricCard({
  label,
  value,
  sublabel,
  icon,
  trend,
  className,
  accent = "default",
}: MetricCardProps) {
  const accentBorder = {
    default: "hover:border-border-default",
    success: "hover:border-success/30",
    danger: "hover:border-danger/30",
    info: "hover:border-info/30",
    warning: "hover:border-warning/30",
    accent: "hover:border-accent/30",
  };

  return (
    <div
      className={cn(
        "rounded-2xl border border-border-subtle bg-bg-secondary/50 p-5 transition-colors",
        accentBorder[accent],
        className
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-bg-tertiary border border-border-subtle flex items-center justify-center shrink-0">
            <span className={iconTone[accent]}>{icon}</span>
          </div>
        )}
        {trend && (
          <span
            className={cn(
              "text-xs font-semibold tabular-nums px-2 py-1 rounded-lg",
              trend.positive
                ? "bg-success/10 text-success"
                : "bg-danger/10 text-danger"
            )}
          >
            {trend.value}
          </span>
        )}
      </div>
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p
        className={cn(
          "text-2xl font-semibold tabular-nums tracking-tight",
          accent !== "default" ? iconTone[accent] : "text-text-primary"
        )}
      >
        {value}
      </p>
      {sublabel && (
        <p className="text-xs text-text-muted mt-2">{sublabel}</p>
      )}
    </div>
  );
}
