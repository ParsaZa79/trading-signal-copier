"use client";

import { Sidebar } from "./sidebar";
import { useWebSocket } from "@/hooks/use-websocket";
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { Position, AccountInfo } from "@/types";
import { Bell, Search, ChevronDown } from "lucide-react";
import { getSymbolPrice } from "@/lib/api";
import { SymbolIcon } from "@/components/dashboard/symbol-icon";

interface PriceData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  prevBid?: number;
}

// Context for sharing WebSocket data across pages
interface DashboardContextType {
  positions: Position[];
  account: AccountInfo | null;
  isConnected: boolean;
  error: string | null;
  reconnect: () => void;
}

const DashboardContext = createContext<DashboardContextType | null>(null);

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardLayout");
  }
  return context;
}

interface DashboardLayoutProps {
  children: ReactNode;
}

// Symbols to show in header - the API will resolve the actual broker name
const HEADER_SYMBOLS = [
  { base: "XAUUSD", label: "XAU/USD" },
  { base: "EURUSD", label: "EUR/USD" },
  { base: "GBPUSD", label: "GBP/USD" },
];

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { positions, account, isConnected, error, reconnect } = useWebSocket();
  const [headerPrices, setHeaderPrices] = useState<Record<string, PriceData>>({});

  const fetchHeaderPrices = useCallback(async () => {
    try {
      const results = await Promise.all(
        HEADER_SYMBOLS.map(async (sym) => {
          try {
            // The API's get_symbol_info handles finding the actual broker symbol
            const price = await getSymbolPrice(sym.base);
            return { base: sym.base, data: price };
          } catch {
            return null;
          }
        })
      );

      setHeaderPrices((prev) => {
        const newPrices: Record<string, PriceData> = {};
        results.forEach((result) => {
          if (result?.data) {
            newPrices[result.base] = {
              ...result.data,
              prevBid: prev[result.base]?.bid,
            };
          }
        });
        return newPrices;
      });
    } catch (error) {
      console.error("Failed to fetch header prices:", error);
    }
  }, []);

  useEffect(() => {
    // Use setTimeout to avoid synchronous setState in effect
    const initialFetch = setTimeout(fetchHeaderPrices, 0);
    const interval = setInterval(fetchHeaderPrices, 2000);
    return () => {
      clearTimeout(initialFetch);
      clearInterval(interval);
    };
  }, [fetchHeaderPrices]);

  return (
    <DashboardContext.Provider
      value={{ positions, account, isConnected, error, reconnect }}
    >
      <div className="flex min-h-screen">
        <Sidebar isConnected={isConnected} />

        <div className="flex-1 flex flex-col min-h-screen">
          {/* Top Header Bar */}
          <header className="h-14 border-b border-border-subtle bg-bg-primary/70 backdrop-blur-xl sticky top-0 z-40">
            <div className="h-full px-4 lg:px-6 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  Portfolio
                </p>
                <p className="text-[11px] text-text-muted truncate hidden sm:block">
                  {isConnected
                    ? "Markets active · Live MT5 feed"
                    : "Waiting for MT5 connection"}
                </p>
              </div>

              <div className="relative hidden md:block flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search symbols, tickets..."
                  className="w-full h-9 pl-10 pr-14 rounded-xl bg-bg-tertiary/80 border border-border-subtle text-sm text-text-primary placeholder:text-text-muted focus:border-border-default focus:ring-0 transition-colors"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-bg-elevated border border-border-subtle">
                  <span className="text-[10px] text-text-muted font-mono">⌘K</span>
                </div>
              </div>

              {/* Right side */}
              <div className="flex items-center gap-4">
                {/* Market Status Pills */}
                <div className="hidden lg:flex items-center gap-3">
                  {HEADER_SYMBOLS.map((sym) => {
                    const price = headerPrices[sym.base];

                    if (!price) {
                      return (
                        <div
                          key={sym.base}
                          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border-subtle bg-bg-tertiary/80"
                        >
                          <SymbolIcon
                            symbol={sym.base}
                            size="sm"
                            className="w-7 h-7 rounded-md"
                          />
                          <span className="text-xs font-medium text-text-secondary">
                            {sym.label}
                          </span>
                          <span className="text-xs text-text-muted tabular-nums animate-pulse">
                            ---
                          </span>
                        </div>
                      );
                    }

                    const change = price.prevBid
                      ? ((price.bid - price.prevBid) / price.prevBid) * 100
                      : 0;

                    return (
                      <MarketPill
                        key={sym.base}
                        symbol={sym.label}
                        iconSymbol={sym.base}
                        value={price.bid.toFixed(price.bid > 100 ? 2 : 5)}
                        change={change}
                      />
                    );
                  })}
                </div>

                {/* Notifications */}
                <button className="relative w-9 h-9 rounded-xl bg-bg-tertiary/80 border border-border-subtle flex items-center justify-center hover:bg-bg-elevated transition-colors">
                  <Bell className="w-4 h-4 text-text-secondary" />
                  {isConnected && (
                    <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-success rounded-full" />
                  )}
                </button>

                <button className="flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-xl bg-bg-tertiary/80 border border-border-subtle hover:bg-bg-elevated transition-colors">
                  <div className="w-7 h-7 rounded-lg bg-bg-elevated border border-border-default flex items-center justify-center">
                    <span className="text-[10px] font-semibold text-text-primary">SC</span>
                  </div>
                  <div className="text-left hidden lg:block">
                    <p className="text-xs font-medium text-text-primary">Trader</p>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-text-muted hidden lg:block" />
                </button>
              </div>
            </div>
          </header>

          {/* Main Content */}
          <main className="flex-1 p-4 lg:p-6 overflow-auto">
            {/* Connection Error Banner */}
            {error && (
              <div className="mb-6 p-4 rounded-xl bg-danger/10 border border-danger/30 flex items-center justify-between animate-fade-in">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-danger/20 flex items-center justify-center">
                    <span className="text-danger font-bold">!</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-danger">Connection Error</p>
                    <p className="text-xs text-text-muted">{error}</p>
                  </div>
                </div>
                <button
                  onClick={reconnect}
                  className="px-4 py-2 rounded-lg bg-danger/20 text-sm font-medium text-danger hover:bg-danger/30 transition-colors"
                >
                  Reconnect
                </button>
              </div>
            )}
            {children}
          </main>
        </div>
      </div>
    </DashboardContext.Provider>
  );
}

// Market status pill component
function MarketPill({
  symbol,
  iconSymbol,
  value,
  change,
}: {
  symbol: string;
  iconSymbol: string;
  value: string;
  change: number;
}) {
  const isPositive = change >= 0;

  return (
    <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border-subtle bg-bg-tertiary/80">
      <SymbolIcon symbol={iconSymbol} size="sm" className="w-7 h-7 rounded-md" />
      <span className="text-xs font-medium text-text-secondary">{symbol}</span>
      <span className="text-xs font-medium text-text-primary tabular-nums">{value}</span>
      <span
        className={`text-[10px] font-semibold tabular-nums px-1.5 py-0.5 rounded ${
          isPositive ? "bg-success/15 text-success" : "bg-danger/15 text-danger"
        }`}
      >
        {isPositive ? "↑" : "↓"} {Math.abs(change).toFixed(2)}%
      </span>
    </div>
  );
}
