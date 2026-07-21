"use client";

import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowDown,
  ArrowUp,
  ChevronRight,
  CircleUserRound,
  History,
  House,
  Link2,
  Plus,
  Repeat2,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";
import type { Position } from "@/types";

const RECENT_DESTINATIONS_KEY = "signal-copier:recent-destinations";
const MAX_RECENT_DESTINATIONS = 3;

type CommandKind = "page" | "market" | "ticket" | "action";
type CommandAction = "new-order" | "review-limits" | "connect-account";

interface CommandDefinition {
  id: string;
  kind: CommandKind;
  label: string;
  description: string;
  keywords: string[];
  icon: LucideIcon;
  href?: string;
  action?: CommandAction;
}

export interface RecentDestination {
  href: string;
  visitedAt: number;
}

interface CommandChoice extends CommandDefinition {
  meta?: string;
}

interface CommandSection {
  id: string;
  label: string;
  items: CommandChoice[];
}

interface CommandDeckProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pathname: string;
  positions: Position[];
  onConnectAccount: () => void;
}

export const PAGE_COMMANDS: readonly CommandDefinition[] = [
  {
    id: "page-home",
    kind: "page",
    label: "Home",
    description: "Account overview and today’s activity",
    keywords: ["overview", "dashboard", "account value"],
    icon: House,
    href: "/",
  },
  {
    id: "page-copy",
    kind: "page",
    label: "Copy trading",
    description: "Find traders and manage copied trades",
    keywords: ["copy", "traders", "subscriptions"],
    icon: Repeat2,
    href: "/copy-trading",
  },
  {
    id: "page-positions",
    kind: "page",
    label: "Positions",
    description: "Review open trades and protection",
    keywords: ["portfolio", "open trades", "tickets"],
    icon: Activity,
    href: "/positions",
  },
  {
    id: "page-history",
    kind: "page",
    label: "Trade history",
    description: "Closed trades and realized P&L",
    keywords: ["portfolio", "closed", "pnl", "performance"],
    icon: History,
    href: "/history",
  },
  {
    id: "page-limits",
    kind: "page",
    label: "Risk & limits",
    description: "Review copy-trading safety settings",
    keywords: ["risk", "safety", "daily loss", "stop"],
    icon: ShieldCheck,
    href: "/copy-trading",
  },
  {
    id: "page-settings",
    kind: "page",
    label: "Account settings",
    description: "Connection status and preferences",
    keywords: ["account", "settings", "preferences", "mt5"],
    icon: CircleUserRound,
    href: "/settings",
  },
] as const;

const QUICK_ACTIONS: readonly CommandDefinition[] = [
  {
    id: "action-new-order",
    kind: "action",
    label: "New order",
    description: "Place a market or pending order",
    keywords: ["buy", "sell", "trade", "execute"],
    icon: Plus,
    action: "new-order",
  },
  {
    id: "action-review-limits",
    kind: "action",
    label: "Review safety limits",
    description: "Check daily loss and copy-risk settings",
    keywords: ["risk", "daily loss", "safety", "copy"],
    icon: ShieldCheck,
    action: "review-limits",
  },
  {
    id: "action-connect-account",
    kind: "action",
    label: "Connect another account",
    description: "Create and configure another MT5 account",
    keywords: ["broker", "mt5", "new account", "connection"],
    icon: Link2,
    action: "connect-account",
  },
] as const;

const DEFAULT_MARKETS = ["XAUUSD", "EURUSD", "GBPUSD"];

function normalizeSearch(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function matchesQuery(command: CommandDefinition, query: string): boolean {
  const normalizedQuery = normalizeSearch(query);
  if (!normalizedQuery) return true;
  const haystack = normalizeSearch(
    [command.label, command.description, ...command.keywords].join(" ")
  );
  return normalizedQuery.split(" ").every((token) => haystack.includes(token));
}

function marketLabel(symbol: string): string {
  const normalized = symbol.toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (normalized.startsWith("XAUUSD")) return "XAU/USD";
  if (normalized.startsWith("EURUSD")) return "EUR/USD";
  if (normalized.startsWith("GBPUSD")) return "GBP/USD";
  if (normalized.startsWith("USDJPY")) return "USD/JPY";
  return symbol.toUpperCase();
}

function marketCommands(positions: Position[]): CommandDefinition[] {
  const symbols = Array.from(
    new Set([...DEFAULT_MARKETS, ...positions.map((position) => position.symbol)])
  );
  return symbols.map((symbol) => ({
    id: `market-${symbol}`,
    kind: "market" as const,
    label: marketLabel(symbol),
    description: `Open an order ticket for ${symbol.toUpperCase()}`,
    keywords: [symbol, marketLabel(symbol), "market", "symbol", "order"],
    icon: SlidersHorizontal,
    href: `/orders?symbol=${encodeURIComponent(symbol)}`,
  }));
}

function ticketCommands(positions: Position[]): CommandDefinition[] {
  return positions.map((position) => ({
    id: `ticket-${position.ticket}`,
    kind: "ticket" as const,
    label: `Ticket #${position.ticket}`,
    description: `${position.type.toUpperCase()} ${position.volume} ${position.symbol}`,
    keywords: [String(position.ticket), position.symbol, position.type, "ticket", "position"],
    icon: Activity,
    href: `/positions?ticket=${position.ticket}`,
  }));
}

export function searchCommandCatalog(
  query: string,
  positions: Position[]
): CommandDefinition[] {
  if (!normalizeSearch(query)) return [];
  return [...PAGE_COMMANDS, ...marketCommands(positions), ...ticketCommands(positions), ...QUICK_ACTIONS]
    .filter((command) => matchesQuery(command, query))
    .slice(0, 12);
}

export function rememberRecentDestination(
  current: RecentDestination[],
  href: string,
  visitedAt: number
): RecentDestination[] {
  if (!PAGE_COMMANDS.some((command) => command.href === href)) return current;
  return [
    { href, visitedAt },
    ...current.filter((destination) => destination.href !== href),
  ].slice(0, MAX_RECENT_DESTINATIONS);
}

export function formatRecentAge(visitedAt: number, now: number): string {
  const elapsed = Math.max(0, now - visitedAt);
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  if (hours < 48) return "Yesterday";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(
    new Date(visitedAt)
  );
}

function loadRecentDestinations(): RecentDestination[] {
  try {
    const stored = window.localStorage.getItem(RECENT_DESTINATIONS_KEY);
    if (!stored) return [];
    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (value): value is RecentDestination =>
        typeof value?.href === "string" && typeof value?.visitedAt === "number"
    );
  } catch {
    return [];
  }
}

function saveRecentDestinations(destinations: RecentDestination[]) {
  try {
    window.localStorage.setItem(RECENT_DESTINATIONS_KEY, JSON.stringify(destinations));
  } catch {
    // Navigation still works when storage is unavailable.
  }
}

function commandForRecent(destination: RecentDestination, now: number): CommandChoice | null {
  const command = PAGE_COMMANDS.find((item) => item.href === destination.href);
  if (!command) return null;
  const recentLabel =
    destination.href === "/positions"
      ? "Open positions"
      : destination.href === "/copy-trading"
        ? "Copy traders"
        : command.label;
  return {
    ...command,
    id: `recent-${command.id}`,
    label: recentLabel,
    meta: formatRecentAge(destination.visitedAt, now),
  };
}

export function CommandDeck({
  open,
  onOpenChange,
  pathname,
  positions,
  onConnectAccount,
}: CommandDeckProps) {
  const router = useRouter();
  const dialogRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const rowRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recentDestinations, setRecentDestinations] = useState<RecentDestination[]>([]);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const current = loadRecentDestinations();
    const next = rememberRecentDestination(current, pathname, Date.now());
    saveRecentDestinations(next);
    const frame = window.requestAnimationFrame(() => setRecentDestinations(next));
    return () => window.cancelAnimationFrame(frame);
  }, [pathname]);

  useEffect(() => {
    const handleGlobalShortcut = (event: globalThis.KeyboardEvent) => {
      if (event.key.toLowerCase() !== "k" || (!event.metaKey && !event.ctrlKey)) return;
      event.preventDefault();
      onOpenChange(!open);
    };
    window.addEventListener("keydown", handleGlobalShortcut);
    return () => window.removeEventListener("keydown", handleGlobalShortcut);
  }, [onOpenChange, open]);

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => {
      setQuery("");
      setSelectedIndex(0);
      setNow(Date.now());
      setRecentDestinations(loadRecentDestinations());
      inputRef.current?.focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
      restoreFocusRef.current?.focus();
    };
  }, [open]);

  const recentItems = useMemo(
    () =>
      recentDestinations
        .map((destination) => commandForRecent(destination, now))
        .filter((item): item is CommandChoice => item !== null),
    [now, recentDestinations]
  );

  const sections = useMemo<CommandSection[]>(() => {
    if (normalizeSearch(query)) {
      return [
        {
          id: "results",
          label: "Search results",
          items: searchCommandCatalog(query, positions),
        },
      ];
    }
    return [
      { id: "recent", label: "Recent", items: recentItems },
      { id: "navigate", label: "Navigate", items: [...PAGE_COMMANDS] },
      { id: "actions", label: "Quick actions", items: [...QUICK_ACTIONS] },
    ].filter((section) => section.items.length > 0);
  }, [positions, query, recentItems]);

  const choices = useMemo(() => sections.flatMap((section) => section.items), [sections]);
  const activeIndex = choices.length ? Math.min(selectedIndex, choices.length - 1) : 0;

  useEffect(() => {
    rowRefs.current[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  const close = () => onOpenChange(false);

  const execute = (command: CommandChoice) => {
    close();
    if (command.href) {
      router.push(command.href);
      return;
    }
    if (command.action === "new-order") {
      router.push("/orders");
      return;
    }
    if (command.action === "review-limits") {
      router.push("/copy-trading");
      return;
    }
    if (command.action === "connect-account") {
      onConnectAccount();
    }
  };

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelectedIndex((current) => (choices.length ? (current + 1) % choices.length : 0));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelectedIndex((current) =>
        choices.length ? (current - 1 + choices.length) % choices.length : 0
      );
      return;
    }
    if (event.key === "Enter" && choices[activeIndex]) {
      event.preventDefault();
      execute(choices[activeIndex]);
      return;
    }
  };

  const handleDialogKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = Array.from(
      dialogRef.current?.querySelectorAll<HTMLElement>(
        'input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      ) ?? []
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!open) return null;

  let commandIndex = -1;

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center px-4 pt-[15vh]">
      <button
        type="button"
        aria-label="Close command menu"
        className="absolute inset-0 cursor-default bg-black/72 backdrop-blur-[2px]"
        onClick={close}
      />
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Command menu"
        onKeyDown={handleDialogKeyDown}
        className="relative flex max-h-[70vh] w-full max-w-[752px] flex-col overflow-hidden rounded-[20px] border border-border-default bg-[#111113] shadow-[0_28px_90px_rgba(0,0,0,0.72)] animate-fade-in"
      >
        <div className="p-5 pb-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-text-muted" />
            <label htmlFor="global-command-search" className="sr-only">
              Search pages, symbols, tickets, or actions
            </label>
            <input
              ref={inputRef}
              id="global-command-search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setSelectedIndex(0);
              }}
              onKeyDown={handleInputKeyDown}
              placeholder="Search pages, symbols, tickets, or actions…"
              autoComplete="off"
              spellCheck={false}
              aria-controls="global-command-results"
              aria-activedescendant={choices[activeIndex]?.id}
              className="h-11 w-full rounded-xl border border-border-default bg-bg-tertiary/75 pl-12 pr-16 text-[15px] text-text-primary outline-none placeholder:text-text-muted focus:border-accent/45 focus:ring-2 focus:ring-accent/10"
            />
            <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-md border border-border-default bg-bg-elevated px-2 py-1 font-mono text-[10px] text-text-muted">
              Esc
            </span>
          </div>
        </div>

        <div
          id="global-command-results"
          role="listbox"
          aria-label="Commands"
          className="min-h-0 flex-1 overflow-y-auto px-5 pb-3"
        >
          {choices.length === 0 ? (
            <div className="flex min-h-48 flex-col items-center justify-center px-6 text-center">
              <Search className="h-6 w-6 text-text-muted" />
              <p className="mt-3 text-sm font-medium text-text-primary">No commands found</p>
              <p className="mt-1 text-xs text-text-muted">
                Try a page, market symbol, ticket number, or action.
              </p>
            </div>
          ) : (
            sections.map((section, sectionIndex) => (
              <div
                key={section.id}
                className={cn(
                  "py-3",
                  sectionIndex > 0 && "border-t border-border-subtle"
                )}
              >
                <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted">
                  {section.label}
                </p>
                <div className="space-y-0.5">
                  {section.items.map((command) => {
                    commandIndex += 1;
                    const currentIndex = commandIndex;
                    const selected = currentIndex === activeIndex;
                    const Icon = command.icon;
                    return (
                      <button
                        key={command.id}
                        ref={(node) => {
                          rowRefs.current[currentIndex] = node;
                        }}
                        id={command.id}
                        type="button"
                        role="option"
                        aria-selected={selected}
                        onMouseEnter={() => setSelectedIndex(currentIndex)}
                        onClick={() => execute(command)}
                        className={cn(
                          "group flex min-h-10 w-full items-center gap-3 rounded-lg border px-3 py-1.5 text-left outline-none",
                          selected
                            ? "border-accent/55 bg-accent/10 text-text-primary shadow-[inset_0_0_0_1px_rgba(138,180,255,0.08)]"
                            : "border-transparent text-text-secondary hover:bg-bg-tertiary/70 hover:text-text-primary"
                        )}
                      >
                        <Icon
                          className={cn(
                            "h-[18px] w-[18px] shrink-0",
                            selected ? "text-accent" : "text-text-muted group-hover:text-text-secondary"
                          )}
                          strokeWidth={1.8}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium">{command.label}</span>
                          {normalizeSearch(query) && (
                            <span className="mt-0.5 block truncate text-[11px] text-text-muted">
                              {command.description}
                            </span>
                          )}
                        </span>
                        {command.meta && (
                          <span className="shrink-0 text-xs text-text-muted">{command.meta}</span>
                        )}
                        {selected ? (
                          <span className="flex shrink-0 items-center gap-1.5 text-xs text-accent">
                            <span className="font-mono">↵</span>
                            Open
                          </span>
                        ) : (
                          <ChevronRight className="h-4 w-4 shrink-0 text-text-muted" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border-subtle bg-bg-primary/45 px-5 py-3 text-[11px] text-text-muted">
          <span className="flex items-center gap-2">
            <KeyHint>
              <ArrowUp className="h-3 w-3" />
              <ArrowDown className="h-3 w-3" />
            </KeyHint>
            Navigate
          </span>
          <span className="flex items-center gap-2">
            <KeyHint>↵</KeyHint>
            Open
          </span>
          <span className="flex items-center gap-2">
            <KeyHint>Esc</KeyHint>
            Close
          </span>
        </footer>
      </section>
    </div>
  );
}

function KeyHint({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex min-h-6 min-w-6 items-center justify-center gap-0.5 rounded-md border border-border-default bg-bg-elevated px-1.5 font-mono text-[10px] text-text-secondary">
      {children}
    </span>
  );
}

export function CommandSearchTrigger({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group relative hidden h-9 min-w-0 flex-1 max-w-md items-center rounded-xl border border-border-subtle bg-bg-tertiary/80 pl-10 pr-14 text-left text-sm text-text-muted transition-colors hover:border-border-default hover:bg-bg-elevated/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/35 md:flex"
      aria-label="Open global search"
    >
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted group-hover:text-text-secondary" />
      <span className="truncate">Search symbols, tickets…</span>
      <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border-subtle bg-bg-elevated px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
        ⌘K
      </span>
    </button>
  );
}
