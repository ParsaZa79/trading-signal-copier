"use client";

import { MobileNav, Sidebar } from "./sidebar";
import { useAuth, useUser } from "@clerk/nextjs";
import { AuthScreen } from "@/components/auth/auth-screen";
import { SymbolIcon } from "@/components/dashboard/symbol-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWebSocket } from "@/hooks/use-websocket";
import {
  activateAccount,
  createAccount,
  getBootstrapStatus,
  getMe,
  getSymbolPrice,
  logout,
} from "@/lib/api";
import { BETTER_AUTH_ENABLED, CLERK_ENABLED } from "@/lib/auth-mode";
import { authClient, getBetterAuthJwt } from "@/lib/auth-client";
import {
  clearStoredSession,
  getStoredSession,
  storeSession,
  type AuthSession,
} from "@/lib/auth-storage";
import { setBetterAuthTokenProvider, setClerkTokenProvider } from "@/lib/clerk-token";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { Position, AccountInfo } from "@/types";
import { Bell, Search, ChevronDown, Loader2, LogOut, Plus, UserRound } from "lucide-react";

interface PriceData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  daily_change_percent?: number | null;
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
  const pathname = usePathname();
  if (pathname.startsWith("/sign-in") || pathname.startsWith("/sign-up")) {
    return <>{children}</>;
  }

  if (
    process.env.NEXT_PUBLIC_COPY_TRADING_PREVIEW === "true" &&
    pathname.startsWith("/copy-trading")
  ) {
    return <CopyTradingPreviewLayout>{children}</CopyTradingPreviewLayout>;
  }

  if (CLERK_ENABLED) {
    return <ClerkDashboardLayout>{children}</ClerkDashboardLayout>;
  }

  if (BETTER_AUTH_ENABLED) {
    return <BetterAuthDashboardLayout>{children}</BetterAuthDashboardLayout>;
  }

  return <LocalAuthDashboardLayout>{children}</LocalAuthDashboardLayout>;
}

function CopyTradingPreviewLayout({ children }: DashboardLayoutProps) {
  const previewSession: AuthSession = {
    token: "design-preview",
    user: { id: "design-preview", email: "preview@example.com", role: "owner" },
    accounts: [
      { id: "preview-live", user_id: "design-preview", name: "Live Account", setup_complete: true },
      { id: "preview-growth", user_id: "design-preview", name: "Growth Account", setup_complete: true },
    ],
    activeAccountId: "preview-live",
    setupComplete: true,
  };
  const previewAccount: AccountInfo = {
    balance: 10_000,
    equity: 10_000,
    margin: 0,
    free_margin: 10_000,
    profit: 0,
  };

  return (
    <DashboardContext.Provider
      value={{
        positions: [],
        account: previewAccount,
        isConnected: true,
        error: null,
        reconnect: () => undefined,
        session: previewSession,
        setSession: () => undefined,
      }}
    >
      <div className="flex min-h-screen bg-bg-primary">
        <Sidebar isConnected accountName="Live Account" accountInitials="LS" />
        <MobileNav />
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-border-subtle bg-bg-primary/90 px-5 backdrop-blur-xl lg:px-7">
            <div>
              <p className="text-sm font-semibold text-text-primary">Live Account</p>
              <p className="mt-0.5 text-[11px] text-success">MT5 connected</p>
            </div>
            <div className="hidden w-full max-w-sm items-center rounded-xl border border-border-subtle bg-bg-secondary/60 px-3 md:flex">
              <Search className="h-4 w-4 text-text-muted" />
              <span className="px-3 py-2.5 text-sm text-text-muted">Search symbols, tickets…</span>
            </div>
            <div className="rounded-xl border border-border-subtle bg-bg-secondary/55 px-3 py-2 text-sm text-text-secondary">
              Live Account
            </div>
          </header>
          <main className="p-4 pb-24 md:pb-4 lg:p-6">{children}</main>
        </div>
      </div>
    </DashboardContext.Provider>
  );
}

function LocalAuthDashboardLayout({ children }: DashboardLayoutProps) {
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

function BetterAuthDashboardLayout({ children }: DashboardLayoutProps) {
  const { data: authSession, isPending } = authClient.useSession();
  const [session, setSessionState] = useState<AuthSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [accessError, setAccessError] = useState<string | null>(null);
  const setSession = useCallback((nextSession: AuthSession) => {
    storeSession(nextSession);
    setSessionState(nextSession);
  }, []);

  useEffect(() => {
    if (isPending) return;
    if (!authSession) {
      clearStoredSession();
      setSessionState(null);
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    let latestToken: string | null = null;
    const resolveToken = async () => {
      latestToken = (await getBetterAuthJwt()) ?? latestToken;
      return latestToken;
    };
    setBetterAuthTokenProvider(resolveToken);
    void (async () => {
      setIsLoading(true);
      setAccessError(null);
      try {
        const token = await resolveToken();
        if (!token) throw new Error("Authentication required");
        const refreshed = await getMe();
        if (!cancelled) setSession({ ...refreshed, token });
      } catch {
        clearStoredSession();
        if (!cancelled) {
          setSessionState(null);
          setAccessError("Access not granted");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      setBetterAuthTokenProvider(null);
    };
  }, [authSession, isPending, setSession]);

  if (isPending || isLoading) return <main className="min-h-screen bg-bg-primary flex items-center justify-center"><p className="text-sm text-text-muted">Loading dashboard...</p></main>;
  if (!authSession) return <ClerkSignedOutScreen />;
  if (accessError || !session) return <main className="min-h-screen bg-bg-primary flex items-center justify-center p-6"><div className="w-full max-w-md rounded-xl border border-border-subtle bg-bg-secondary p-6"><h1 className="text-xl font-semibold text-text-primary">Access not granted</h1><p className="mt-2 text-sm text-text-muted">Your account is not allowed to access this dashboard.</p><Button className="mt-5" variant="outline" onClick={() => authClient.signOut({ fetchOptions: { onSuccess: () => { window.location.href = "/sign-in"; } } })}>Sign out</Button></div></main>;
  return <AuthenticatedDashboardLayout session={session} setSession={setSession} onLogout={async () => { await authClient.signOut(); window.location.href = "/sign-in"; }}>{children}</AuthenticatedDashboardLayout>;
}

function ClerkDashboardLayout({ children }: DashboardLayoutProps) {
  const { getToken, isLoaded, isSignedIn, signOut } = useAuth();
  const { user } = useUser();
  const [session, setSessionState] = useState<AuthSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [accessError, setAccessError] = useState<string | null>(null);

  const setSession = useCallback((nextSession: AuthSession) => {
    storeSession(nextSession);
    setSessionState(nextSession);
  }, []);

  useEffect(() => {
    if (!isLoaded) return;

    if (!isSignedIn) {
      clearStoredSession();
      setSessionState(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    let latestToken: string | null = null;
    const resolveToken = async () => {
      const freshToken = await getToken();
      if (freshToken) {
        latestToken = freshToken;
      }
      return latestToken;
    };
    setClerkTokenProvider(resolveToken);

    async function loadSession() {
      setIsLoading(true);
      setAccessError(null);
      try {
        const token = await resolveToken();
        if (!token) throw new Error("Authentication required");
        const refreshed = await getMe();
        if (!cancelled) {
          setSession({
            ...refreshed,
            token,
            user: {
              ...refreshed.user,
              email: refreshed.user.email || user?.primaryEmailAddress?.emailAddress || "",
            },
          });
        }
      } catch (error) {
        clearStoredSession();
        if (!cancelled) {
          setSessionState(null);
          setAccessError(error instanceof Error ? error.message : "Access not granted");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadSession();
    return () => {
      cancelled = true;
      setClerkTokenProvider(null);
    };
  }, [getToken, isLoaded, isSignedIn, setSession, user?.primaryEmailAddress?.emailAddress]);

  if (!isLoaded || isLoading) {
    return (
      <main className="min-h-screen bg-bg-primary flex items-center justify-center">
        <p className="text-sm text-text-muted">Loading dashboard...</p>
      </main>
    );
  }

  if (!isSignedIn) {
    return <ClerkSignedOutScreen />;
  }

  if (accessError || !session) {
    return (
      <main className="min-h-screen bg-bg-primary flex items-center justify-center p-6">
        <div className="w-full max-w-md rounded-xl border border-border-subtle bg-bg-secondary p-6">
          <p className="text-xs uppercase tracking-wider text-text-muted">Access</p>
          <h1 className="mt-2 text-xl font-semibold text-text-primary">Access not granted</h1>
          <p className="mt-2 text-sm text-text-muted">
            Your Clerk sign-in worked, but this email is not allowed in the trading dashboard.
          </p>
          {accessError && <p className="mt-3 text-xs text-danger">{accessError}</p>}
          <Button
            className="mt-5"
            variant="outline"
            onClick={() => signOut({ redirectUrl: "/sign-in" })}
          >
            Sign out
          </Button>
        </div>
      </main>
    );
  }

  return (
    <AuthenticatedDashboardLayout
      session={session}
      setSession={setSession}
      onLogout={() => signOut({ redirectUrl: "/sign-in" })}
    >
      {children}
    </AuthenticatedDashboardLayout>
  );
}

function ClerkSignedOutScreen() {
  return (
    <main className="min-h-screen bg-bg-primary flex items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-xl border border-border-subtle bg-bg-secondary p-6">
        <p className="text-xs uppercase tracking-wider text-text-muted">Access</p>
        <h1 className="mt-2 text-xl font-semibold text-text-primary">Sign in required</h1>
        <p className="mt-2 text-sm text-text-muted">
          Use your approved Clerk account to open the trading dashboard.
        </p>
        <Link
          href="/sign-in"
          className="mt-5 inline-flex h-10 items-center justify-center rounded-xl bg-text-primary px-4 text-sm font-semibold text-bg-primary hover:bg-text-secondary"
        >
          Sign in
        </Link>
      </div>
    </main>
  );
}

function AuthenticatedDashboardLayout({
  children,
  session,
  setSession,
  onLogout,
}: {
  children: ReactNode;
  session: AuthSession;
  setSession: (session: AuthSession) => void;
  onLogout?: () => Promise<void> | void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const isSetupRoute = pathname.startsWith("/setup");
  const isPlatformRoute = pathname.startsWith("/copy-trading");
  const needsSetup = !session.setupComplete;
  const shouldForceSetup = needsSetup && !isSetupRoute && !isPlatformRoute;
  const { positions, account, isConnected, error, reconnect } = useWebSocket({
    enabled: session.setupComplete && Boolean(session.activeAccountId),
    token: session.token,
    accountId: session.activeAccountId,
  });
  const [headerPrices, setHeaderPrices] = useState<Record<string, PriceData>>({});
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [createAccountOpen, setCreateAccountOpen] = useState(false);
  const [newAccountName, setNewAccountName] = useState("");
  const [isCreatingAccount, setIsCreatingAccount] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  const completedAccounts = session.accounts.filter((item) => item.setup_complete);
  const activeAccount =
    completedAccounts.find((item) => item.id === session.activeAccountId) ??
    session.accounts.find((item) => item.id === session.activeAccountId) ??
    completedAccounts[0] ??
    session.accounts[0];
  const visibleActiveAccount = needsSetup ? null : activeAccount;
  const mt5Connected = isConnected && account !== null;

  useEffect(() => {
    if (shouldForceSetup) {
      router.replace("/setup");
    } else if (!needsSetup && isSetupRoute) {
      router.replace("/");
    }
  }, [isSetupRoute, needsSetup, router, shouldForceSetup]);

  const fetchHeaderPrices = useCallback(async () => {
    if (!account) {
      setHeaderPrices({});
      return;
    }

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

      setHeaderPrices(() => {
        const newPrices: Record<string, PriceData> = {};
        results.forEach((result) => {
          if (result?.data) {
            newPrices[result.base] = result.data;
          }
        });
        return newPrices;
      });
    } catch (err) {
      console.error("Failed to fetch header prices:", err);
    }
  }, [account]);

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

  const handleCreateAccountSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newAccountName.trim();
    if (!name) return;

    setIsCreatingAccount(true);
    setAccountError(null);
    try {
      const created = await createAccount(name);
      const activated = await activateAccount(created.account.id);
      setSession({
        ...session,
        accounts: activated.accounts,
        activeAccountId: activated.active_account_id,
        setupComplete: false,
      });
      setHeaderPrices({});
      setNewAccountName("");
      setCreateAccountOpen(false);
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : "Could not create account");
    } finally {
      setIsCreatingAccount(false);
    }
  };

  const handleLogout = async () => {
    if (onLogout) {
      await onLogout();
      return;
    }
    await logout();
    window.location.reload();
  };

  if (shouldForceSetup) {
    return (
      <main className="min-h-screen bg-bg-primary flex items-center justify-center">
        <p className="text-sm text-text-muted">Opening account setup...</p>
      </main>
    );
  }

  return (
    <DashboardContext.Provider
      value={{ positions, account, isConnected: mt5Connected, error, reconnect, session, setSession }}
    >
      <div className="flex min-h-screen">
        <Sidebar
          isConnected={mt5Connected}
          accountName={visibleActiveAccount?.name || (needsSetup ? "Account Setup" : "Live Account")}
        />
        <MobileNav />

        <div className="flex-1 flex flex-col min-h-screen">
          <header className="h-14 border-b border-border-subtle bg-bg-primary/70 backdrop-blur-xl sticky top-0 z-40">
            <div className="h-full px-4 lg:px-6 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  {visibleActiveAccount?.name || (needsSetup ? "Account Setup" : "Portfolio")}
                </p>
                <p className="text-[11px] text-text-muted truncate hidden sm:block">
                  {needsSetup
                    ? "Account setup required"
                    : mt5Connected
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
                  {!needsSetup && HEADER_SYMBOLS.map((sym) => {
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

                    const change = price.daily_change_percent ?? 0;

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
                  {mt5Connected && (
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
                        {visibleActiveAccount?.name || session.user.email}
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
                        {completedAccounts.length === 0 && (
                          <div className="px-3 py-2 text-xs text-text-muted">
                            No configured accounts yet.
                          </div>
                        )}
                        {completedAccounts.map((item) => (
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
                          {session.setupComplete && (
                            <button
                              onClick={() => {
                                setAccountMenuOpen(false);
                                setCreateAccountOpen(true);
                              }}
                              className="w-full px-3 py-2 text-left text-sm text-text-secondary hover:bg-bg-tertiary hover:text-text-primary rounded-lg transition-colors flex items-center gap-2"
                            >
                              <Plus className="w-4 h-4" />
                              New account
                            </button>
                          )}
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

          <main className="flex-1 overflow-auto p-4 pb-24 md:pb-4 lg:p-6">
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

          {createAccountOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
              <form
                onSubmit={handleCreateAccountSubmit}
                className="w-full max-w-sm rounded-xl border border-border-subtle bg-bg-elevated p-5 shadow-xl"
              >
                <div className="mb-4">
                  <p className="text-sm font-semibold text-text-primary">New Account</p>
                  <p className="text-xs text-text-muted mt-1">
                    Create an isolated MT5 trading account.
                  </p>
                </div>
                <Input
                  label="Account Name"
                  value={newAccountName}
                  onChange={(event) => setNewAccountName(event.target.value)}
                  placeholder="Broker account"
                  autoFocus
                />
                {accountError && (
                  <div className="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2">
                    <p className="text-xs text-danger">{accountError}</p>
                  </div>
                )}
                <div className="mt-5 flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setCreateAccountOpen(false);
                      setNewAccountName("");
                      setAccountError(null);
                    }}
                    disabled={isCreatingAccount}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="accent"
                    disabled={isCreatingAccount || !newAccountName.trim()}
                  >
                    {isCreatingAccount && <Loader2 className="w-4 h-4 animate-spin" />}
                    <span>Create</span>
                  </Button>
                </div>
              </form>
            </div>
          )}
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
