"use client";

import { Sidebar } from "./sidebar";
import { AuthScreen } from "@/components/auth/auth-screen";
import { SymbolIcon } from "@/components/dashboard/symbol-icon";
import { useWebSocket } from "@/hooks/use-websocket";
import {
  activateAccount,
  createAccount,
  getBootstrapStatus,
  getMe,
  getSymbolPrice,
  logout,
} from "@/lib/api";
import {
  clearStoredSession,
  getStoredSession,
  storeSession,
  type AuthSession,
} from "@/lib/auth-storage";
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { Position, AccountInfo } from "@/types";
import { Bell, Search, ChevronDown, LogOut, Plus, UserRound } from "lucide-react";

interface PriceData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  prevBid?: number;
}

interface DashboardContextType {
  positions: Position[];
  account: AccountInfo | null;
  isConnected: boolean;
  error: string | null;
  reconnect: () => void;
  session: AuthSession;
  setSession: (session: AuthSession) => void;
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

const HEADER_SYMBOLS = [
  { base: "XAUUSD", label: "XAU/USD" },
  { base: "EURUSD", label: "EUR/USD" },
  { base: "GBPUSD", label: "GBP/USD" },
];

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [session, setSessionState] = useState<AuthSession | null>(null);
  const [setupRequired, setSetupRequired] = useState(false);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  const setSession = useCallback((nextSession: AuthSession) => {
    storeSession(nextSession);
    setSessionState(nextSession);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const stored = getStoredSession();
      if (stored) {
        setSessionState(stored);
        try {
          const refreshed = await getMe();
          if (!cancelled) {
            setSessionState(refreshed);
          }
        } catch {
          clearStoredSession();
          if (!cancelled) setSessionState(null);
        }
      }

      try {
        const status = await getBootstrapStatus();
        if (!cancelled) {
          setSetupRequired(status.setup_required);
        }
      } catch {
        if (!cancelled) setSetupRequired(false);
      } finally {
        if (!cancelled) setIsLoadingAuth(false);
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  if (isLoadingAuth) {
    return (
      <main className="min-h-screen bg-bg-primary flex items-center justify-center">
        <p className="text-sm text-text-muted">Loading dashboard...</p>
      </main>
    );
  }

  if (!session) {
    return (
      <AuthScreen
        setupRequired={setupRequired}
        onAuthenticated={(nextSession) => {
          setSetupRequired(false);
          setSession(nextSession);
        }}
      />
    );
  }

  return (
    <AuthenticatedDashboardLayout session={session} setSession={setSession}>
      {children}
    </AuthenticatedDashboardLayout>
  );
}

function AuthenticatedDashboardLayout({
  children,
  session,
  setSession,
}: {
  children: ReactNode;
  session: AuthSession;
  setSession: (session: AuthSession) => void;
}) {
  const { positions, account, isConnected, error, reconnect } = useWebSocket({
    enabled: true,
    token: session.token,
    accountId: session.activeAccountId,
  });
  const [headerPrices, setHeaderPrices] = useState<Record<string, PriceData>>({});
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  const activeAccount =
    session.accounts.find((item) => item.id === session.activeAccountId) ?? session.accounts[0];

  const fetchHeaderPrices = useCallback(async () => {
    try {
      const results = await Promise.all(
        HEADER_SYMBOLS.map(async (sym) => {
          try {
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
    } catch (err) {
      console.error("Failed to fetch header prices:", err);
    }
  }, []);

  useEffect(() => {
    const initialFetch = setTimeout(fetchHeaderPrices, 0);
    const interval = setInterval(fetchHeaderPrices, 2000);
    return () => {
      clearTimeout(initialFetch);
      clearInterval(interval);
    };
  }, [fetchHeaderPrices, session.activeAccountId]);

  const handleSwitchAccount = async (accountId: string) => {
    const result = await activateAccount(accountId);
    const nextSession = {
      ...session,
      accounts: result.accounts,
      activeAccountId: result.active_account_id,
    };
    setHeaderPrices({});
    setSession(nextSession);
    setAccountMenuOpen(false);
  };

  const handleCreateAccount = async () => {
    const name = window.prompt("Account name");
    if (!name?.trim()) return;
    const created = await createAccount(name.trim());
    const activated = await activateAccount(created.account.id);
    setSession({
      ...session,
      accounts: activated.accounts,
      activeAccountId: activated.active_account_id,
    });
    setHeaderPrices({});
    setAccountMenuOpen(false);
  };

  const handleLogout = async () => {
    await logout();
    window.location.reload();
  };

  return (
    <DashboardContext.Provider
      value={{ positions, account, isConnected, error, reconnect, session, setSession }}
    >
      <div className="flex min-h-screen">
        <Sidebar isConnected={isConnected} />

        <div className="flex-1 flex flex-col min-h-screen">
          <header className="h-14 border-b border-border-subtle bg-bg-primary/70 backdrop-blur-xl sticky top-0 z-40">
            <div className="h-full px-4 lg:px-6 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  {activeAccount?.name || "Portfolio"}
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

              <div className="flex items-center gap-4">
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

                <button className="relative w-9 h-9 rounded-xl bg-bg-tertiary/80 border border-border-subtle flex items-center justify-center hover:bg-bg-elevated transition-colors">
                  <Bell className="w-4 h-4 text-text-secondary" />
                  {isConnected && (
                    <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-success rounded-full" />
                  )}
                </button>

                <div className="relative">
                  <button
                    onClick={() => setAccountMenuOpen((open) => !open)}
                    className="flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-xl bg-bg-tertiary/80 border border-border-subtle hover:bg-bg-elevated transition-colors"
                  >
                    <div className="w-7 h-7 rounded-lg bg-bg-elevated border border-border-default flex items-center justify-center">
                      <UserRound className="w-3.5 h-3.5 text-text-primary" />
                    </div>
                    <div className="text-left hidden lg:block max-w-36">
                      <p className="text-xs font-medium text-text-primary truncate">
                        {activeAccount?.name || session.user.email}
                      </p>
                    </div>
                    <ChevronDown className="w-3.5 h-3.5 text-text-muted hidden lg:block" />
                  </button>

                  {accountMenuOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-10"
                        onClick={() => setAccountMenuOpen(false)}
                      />
                      <div className="absolute right-0 top-full mt-2 w-64 p-2 rounded-xl bg-bg-elevated border border-border-subtle shadow-lg z-20">
                        <div className="px-3 py-2 border-b border-border-subtle mb-1">
                          <p className="text-xs font-medium text-text-primary truncate">
                            {session.user.email}
                          </p>
                        </div>
                        {session.accounts.map((item) => (
                          <button
                            key={item.id}
                            onClick={() => handleSwitchAccount(item.id)}
                            className={`w-full px-3 py-2 text-left text-sm rounded-lg transition-colors ${
                              item.id === session.activeAccountId
                                ? "bg-accent/20 text-accent"
                                : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                            }`}
                          >
                            {item.name}
                          </button>
                        ))}
                        <div className="border-t border-border-subtle mt-2 pt-2 space-y-1">
                          <button
                            onClick={handleCreateAccount}
                            className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-bg-tertiary hover:text-text-primary rounded-lg transition-colors flex items-center gap-2"
                          >
                            <Plus className="w-4 h-4" />
                            New account
                          </button>
                          <button
                            onClick={handleLogout}
                            className="w-full px-3 py-2 text-left text-sm text-danger hover:bg-danger/10 rounded-lg transition-colors flex items-center gap-2"
                          >
                            <LogOut className="w-4 h-4" />
                            Sign out
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </header>

          <main className="flex-1 p-4 lg:p-6 overflow-auto">
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
