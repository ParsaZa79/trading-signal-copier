"use client";

import { cn } from "@/lib/utils";

export type TimeRange = "1D" | "1W" | "1M" | "3M" | "YTD" | "1Y";

const RANGES: TimeRange[] = ["1D", "1W", "1M", "3M", "YTD", "1Y"];

interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
  className?: string;
}

export function TimeRangeSelector({
  value,
  onChange,
  className,
}: TimeRangeSelectorProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-0.5 p-1 rounded-xl bg-bg-tertiary/80 border border-border-subtle",
        className
      )}
    >
      {RANGES.map((range) => (
        <button
          key={range}
          type="button"
          onClick={() => onChange(range)}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs font-medium tabular-nums transition-all",
            value === range
              ? "bg-bg-elevated text-text-primary shadow-sm border border-border-default"
              : "text-text-muted hover:text-text-secondary"
          )}
        >
          {range}
        </button>
      ))}
    </div>
  );
}

export function getDateRangeForTimeRange(range: TimeRange): {
  from: string;
  to: string;
} {
  const now = new Date();
  const to = new Date(now);
  to.setDate(to.getDate() + 1);

  const from = new Date(now);

  switch (range) {
    case "1D":
      from.setDate(from.getDate() - 1);
      break;
    case "1W":
      from.setDate(from.getDate() - 7);
      break;
    case "1M":
      from.setMonth(from.getMonth() - 1);
      break;
    case "3M":
      from.setMonth(from.getMonth() - 3);
      break;
    case "YTD":
      from.setMonth(0, 1);
      break;
    case "1Y":
      from.setFullYear(from.getFullYear() - 1);
      break;
  }

  return {
    from: from.toISOString().split("T")[0],
    to: to.toISOString().split("T")[0],
  };
}
