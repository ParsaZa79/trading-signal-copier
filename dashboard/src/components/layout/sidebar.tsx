"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  TrendingUp,
  History,
  Settings,
  Activity,
  Plus,
  Bot,
  Sliders,
  BarChart3,
  ShieldCheck,
  Network,
  Repeat2,
  Shield,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/platform", label: "Platform", icon: Network },
  { href: "/copy-trading", label: "Copy", icon: Repeat2 },
  { href: "/risk", label: "Risk", icon: Shield },
  { href: "/bot", label: "Bot", icon: Bot },
  { href: "/config", label: "Config", icon: Sliders },
  { href: "/positions", label: "Positions", icon: Activity },
  { href: "/analysis", label: "Analysis", icon: BarChart3 },
  { href: "/orders", label: "Orders", icon: Plus },
  { href: "/history", label: "History", icon: History },
  { href: "/access", label: "Access", icon: ShieldCheck },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface SidebarProps {
  isConnected: boolean;
}

export function Sidebar({ isConnected }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="w-[72px] xl:w-[220px] h-screen flex flex-col border-r border-border-subtle bg-bg-primary/80 backdrop-blur-xl sticky top-0 shrink-0">
      <div className="p-4 xl:px-5 xl:py-6 flex-shrink-0">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-bg-elevated border border-border-default flex items-center justify-center shrink-0">
            <TrendingUp className="w-5 h-5 text-text-primary" />
          </div>
          <div className="hidden xl:block min-w-0">
            <h1 className="text-sm font-semibold text-text-primary tracking-tight truncate">
              Signal Copier
            </h1>
            <p className="text-[10px] text-text-muted truncate">MT5 Dashboard</p>
          </div>
        </Link>
      </div>

      <nav className="flex-1 px-2 xl:px-3 overflow-y-auto min-h-0">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  title={item.label}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors",
                    isActive
                      ? "bg-bg-elevated text-text-primary border border-border-default"
                      : "text-text-muted hover:text-text-secondary hover:bg-bg-tertiary/60"
                  )}
                >
                  <Icon
                    className={cn(
                      "w-[18px] h-[18px] shrink-0",
                      isActive && "text-accent"
                    )}
                  />
                  <span className="hidden xl:block text-sm font-medium truncate">
                    {item.label}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="flex-shrink-0 p-3 xl:p-4 border-t border-border-subtle">
        <div className="flex items-center gap-2 xl:gap-3 px-2 xl:px-3 py-2.5 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
          <span
            className={cn(
              "relative flex h-2 w-2 rounded-full shrink-0",
              isConnected ? "bg-success" : "bg-danger"
            )}
          >
            {isConnected && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" />
            )}
          </span>
          <div className="hidden xl:block min-w-0">
            <p className="text-xs font-medium text-text-primary truncate">
              {isConnected ? "Connected" : "Offline"}
            </p>
            <p className="text-[10px] text-text-muted truncate">MT5 Terminal</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
