"use client";

import { cn } from "@/lib/utils";

interface PerformanceBar {
  label: string;
  value: number;
  display: string;
  tone?: "success" | "danger" | "neutral" | "accent";
}

interface PerformancePanelProps {
  title?: string;
  bars: PerformanceBar[];
  className?: string;
}

export function PerformancePanel({
  title = "Performance",
  bars,
  className,
}: PerformancePanelProps) {
  const max = Math.max(...bars.map((b) => b.value), 1);

  return (
    <section
      className={cn(
        "rounded-2xl border border-border-subtle bg-bg-secondary/50 p-5",
        className
      )}
    >
      <h3 className="text-sm font-semibold text-text-primary mb-4">{title}</h3>
      <ul className="space-y-4">
        {bars.map((bar) => (
          <li key={bar.label}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-text-secondary">{bar.label}</span>
              <span
                className={cn(
                  "text-xs font-semibold tabular-nums",
                  bar.tone === "success"
                    ? "text-success"
                    : bar.tone === "danger"
                      ? "text-danger"
                      : bar.tone === "accent"
                        ? "text-accent"
                        : "text-text-primary"
                )}
              >
                {bar.display}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  bar.tone === "success"
                    ? "bg-success"
                    : bar.tone === "danger"
                      ? "bg-danger"
                      : bar.tone === "accent"
                        ? "bg-accent"
                        : "bg-text-secondary"
                )}
                style={{ width: `${(bar.value / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
