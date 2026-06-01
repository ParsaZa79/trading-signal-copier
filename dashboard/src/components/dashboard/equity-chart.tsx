"use client";

import { cn } from "@/lib/utils";

export interface ChartPoint {
  label: string;
  value: number;
}

interface EquityChartProps {
  data: ChartPoint[];
  positive?: boolean;
  className?: string;
  height?: number;
}

export function EquityChart({
  data,
  positive = true,
  className,
  height = 120,
}: EquityChartProps) {
  if (data.length < 2) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-xl bg-bg-tertiary/40 border border-border-subtle",
          className
        )}
        style={{ height }}
      >
        <p className="text-xs text-text-muted">Not enough data for chart</p>
      </div>
    );
  }

  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const padding = 8;
  const width = 100;

  const points = data
    .map((point, index) => {
      const x = (index / (data.length - 1)) * width;
      const y =
        height -
        padding -
        ((point.value - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  const areaPoints = `0,${height} ${points} ${width},${height}`;
  const stroke = positive ? "var(--success)" : "var(--danger)";
  const fill = positive ? "var(--success-muted)" : "var(--danger-muted)";

  return (
    <div className={cn("relative w-full", className)} style={{ height }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="w-full h-full"
      >
        <defs>
          <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={fill} stopOpacity="0.5" />
            <stop offset="100%" stopColor={fill} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={areaPoints} fill="url(#chartFill)" />
        <polyline
          points={points}
          fill="none"
          stroke={stroke}
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

export function buildEquityCurve(
  trades: { closed_at: string; profit: number }[],
  baseEquity: number
): ChartPoint[] {
  const sorted = [...trades].sort(
    (a, b) => new Date(a.closed_at).getTime() - new Date(b.closed_at).getTime()
  );

  if (sorted.length === 0) {
    return [
      { label: "start", value: baseEquity },
      { label: "now", value: baseEquity },
    ];
  }

  let running = baseEquity - sorted.reduce((sum, t) => sum + t.profit, 0);
  const points: ChartPoint[] = [
    {
      label: "start",
      value: running,
    },
  ];

  for (const trade of sorted) {
    running += trade.profit;
    points.push({
      label: trade.closed_at,
      value: running,
    });
  }

  points.push({ label: "now", value: baseEquity });

  return points;
}
