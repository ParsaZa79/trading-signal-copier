import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface SectionPanelProps {
  children: ReactNode;
  className?: string;
}

export function SectionPanel({ children, className }: SectionPanelProps) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-border-subtle bg-bg-secondary/50 overflow-hidden",
        className
      )}
    >
      {children}
    </section>
  );
}

interface PanelHeaderProps {
  eyebrow?: string;
  title: ReactNode;
  description?: string;
  action?: ReactNode;
  metric?: { label: string; value: ReactNode; tone?: "default" | "success" | "danger" | "accent" };
  className?: string;
}

export function PanelHeader({
  eyebrow,
  title,
  description,
  action,
  metric,
  className,
}: PanelHeaderProps) {
  const toneClass = {
    default: "text-text-primary",
    success: "text-success",
    danger: "text-danger",
    accent: "text-accent",
  };

  return (
    <div
      className={cn(
        "px-5 py-4 sm:px-6 sm:py-5 border-b border-border-subtle flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className
      )}
    >
      <div className="min-w-0">
        {eyebrow && (
          <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted mb-2">
            {eyebrow}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold text-text-primary">{title}</h2>
        </div>
        {description && (
          <p className="text-xs text-text-muted mt-1">{description}</p>
        )}
        {metric && (
          <div className="mt-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted mb-1">
              {metric.label}
            </p>
            <p
              className={cn(
                "text-2xl font-semibold tabular-nums",
                toneClass[metric.tone ?? "default"]
              )}
            >
              {metric.value}
            </p>
          </div>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

interface PanelBodyProps {
  children: ReactNode;
  className?: string;
  flush?: boolean;
}

export function PanelBody({ children, className, flush }: PanelBodyProps) {
  return (
    <div className={cn(!flush && "p-5 sm:p-6", className)}>{children}</div>
  );
}

interface TerminalPanelProps {
  children: ReactNode;
  className?: string;
  height?: string;
}

export function TerminalPanel({
  children,
  className,
  height = "h-96",
}: TerminalPanelProps) {
  return (
    <div
      className={cn(
        "overflow-y-auto bg-[#070708] border-t border-border-subtle font-mono text-xs leading-relaxed",
        height,
        className
      )}
    >
      <div className="p-4">{children}</div>
    </div>
  );
}
