import { API_URL } from "./constants";
import {
  clearStoredSession,
  getActiveAccountId,
  getAuthToken,
  storeSession,
  type AuthSession,
  type DashboardAccount,
} from "./auth-storage";
import type {
  Position,
  AccountInfo,
  HealthStatus,
  PlaceOrderRequest,
  PendingOrder,
  TradeHistoryEntry,
  MT5ConnectResponse,
} from "@/types";

function toBrokerSymbol(symbol: string): string {
  const normalized = symbol.trim().toUpperCase();
  if (!normalized) {
    return normalized;
  }
  return normalized.endsWith("B") ? normalized : `${normalized}b`;
}

/**
 * Fetch wrapper with error handling
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const headers = new Headers(options?.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const token = getAuthToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const accountId = getActiveAccountId();
  if (accountId) {
    headers.set("X-Account-Id", accountId);
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    if (response.status === 401) {
      clearStoredSession();
    }
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

function normalizeAuthSession(response: {
  token: string;
  user: AuthSession["user"];
  accounts: DashboardAccount[];
  active_account_id: string;
}): AuthSession {
  return {
    token: response.token,
    user: response.user,
    accounts: response.accounts,
    activeAccountId: response.active_account_id,
  };
}

export async function getBootstrapStatus(): Promise<{ setup_required: boolean }> {
  return fetchApi("/api/auth/bootstrap");
}

export async function setupAdmin(email: string, password: string): Promise<AuthSession> {
  const response = await fetchApi<{
    token: string;
    user: AuthSession["user"];
    accounts: DashboardAccount[];
    active_account_id: string;
  }>("/api/auth/setup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const session = normalizeAuthSession(response);
  storeSession(session);
  return session;
}

export async function login(email: string, password: string): Promise<AuthSession> {
  const response = await fetchApi<{
    token: string;
    user: AuthSession["user"];
    accounts: DashboardAccount[];
    active_account_id: string;
  }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const session = normalizeAuthSession(response);
  storeSession(session);
  return session;
}

export async function getMe(): Promise<AuthSession> {
  const response = await fetchApi<{
    user: AuthSession["user"];
    accounts: DashboardAccount[];
    active_account_id: string;
  }>("/api/auth/me");
  const existing = getAuthToken();
  if (!existing) {
    throw new Error("Authentication required");
  }
  const session: AuthSession = {
    token: existing,
    user: response.user,
    accounts: response.accounts,
    activeAccountId: response.active_account_id,
  };
  storeSession(session);
  return session;
}

export async function logout(): Promise<void> {
  await fetchApi("/api/auth/logout", { method: "POST" }).catch(() => undefined);
  clearStoredSession();
}

export async function getAccounts(): Promise<{
  success: boolean;
  accounts: DashboardAccount[];
  active_account_id: string;
}> {
  return fetchApi("/api/accounts");
}

export async function createAccount(name: string): Promise<{
  success: boolean;
  account: DashboardAccount;
  accounts: DashboardAccount[];
}> {
  return fetchApi("/api/accounts", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function activateAccount(accountId: string): Promise<{
  success: boolean;
  account: DashboardAccount;
  active_account_id: string;
  accounts: DashboardAccount[];
}> {
  return fetchApi(`/api/accounts/${encodeURIComponent(accountId)}/active`, {
    method: "PUT",
  });
}

// Health
export async function getHealth(): Promise<HealthStatus> {
  return fetchApi("/api/health");
}

export async function connectMT5(
  config: Record<string, string>
): Promise<MT5ConnectResponse> {
  const dockerPort = config.MT5_DOCKER_PORT?.trim();
  return fetchApi("/api/mt5/connect", {
    method: "POST",
    body: JSON.stringify({
      login: config.MT5_LOGIN ? Number(config.MT5_LOGIN) : undefined,
      password: config.MT5_PASSWORD || undefined,
      server: config.MT5_SERVER || undefined,
      docker_host: config.MT5_DOCKER_HOST || undefined,
      docker_port: dockerPort ? Number(dockerPort) : undefined,
      path: config.MT5_PATH || undefined,
    }),
  });
}

// Positions
export async function getPositions(): Promise<Position[]> {
  return fetchApi("/api/positions");
}

export async function getPosition(ticket: number): Promise<Position> {
  return fetchApi(`/api/positions/${ticket}`);
}

export async function modifyPosition(
  ticket: number,
  sl?: number,
  tp?: number
): Promise<{ success: boolean; error?: string }> {
  return fetchApi(`/api/positions/${ticket}`, {
    method: "PUT",
    body: JSON.stringify({ sl, tp }),
  });
}

export async function closePosition(
  ticket: number
): Promise<{ success: boolean; error?: string }> {
  return fetchApi(`/api/positions/${ticket}`, {
    method: "DELETE",
  });
}

// Orders
export async function placeOrder(
  order: PlaceOrderRequest
): Promise<{ success: boolean; ticket?: number; error?: string }> {
  const normalizedOrder: PlaceOrderRequest = {
    ...order,
    symbol: toBrokerSymbol(order.symbol),
  };
  return fetchApi("/api/orders", {
    method: "POST",
    body: JSON.stringify(normalizedOrder),
  });
}

export async function getPendingOrders(
  symbol?: string
): Promise<PendingOrder[]> {
  const query = symbol ? `?symbol=${toBrokerSymbol(symbol)}` : "";
  return fetchApi(`/api/orders/pending${query}`);
}

export async function cancelOrder(
  ticket: number
): Promise<{ success: boolean; error?: string }> {
  return fetchApi(`/api/orders/${ticket}`, {
    method: "DELETE",
  });
}

// Account
export async function getAccountInfo(): Promise<AccountInfo> {
  return fetchApi("/api/account");
}

export async function getTradeHistory(
  page: number = 1,
  pageSize: number = 50,
  symbol?: string,
  fromDate?: string,
  toDate?: string
): Promise<{ trades: TradeHistoryEntry[]; total: number }> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  });
  if (symbol) params.set("symbol", toBrokerSymbol(symbol));
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  return fetchApi(`/api/account/history?${params}`);
}

// Symbols
export interface SymbolListItem {
  value: string;
  label: string;
}

export async function getSymbols(): Promise<SymbolListItem[]> {
  return fetchApi("/api/symbols");
}

export async function getSymbolPrice(
  symbol: string
): Promise<{ symbol: string; bid: number; ask: number; spread: number }> {
  return fetchApi(`/api/symbols/${toBrokerSymbol(symbol)}/price`);
}

// ============================================================
// Bot Management APIs (FastAPI backend)
// ============================================================

// Bot Config
export async function getBotConfig(): Promise<{
  success: boolean;
  account_id: string;
  config: Record<string, string>;
  configuredSecrets: string[];
  secretFields: string[];
}> {
  return fetchApi("/api/config");
}

export async function saveBotConfig(
  config: Record<string, string>,
  writeEnv = false
): Promise<{ success: boolean; configuredSecrets?: string[] }> {
  return fetchApi("/api/config", {
    method: "PUT",
    body: JSON.stringify({ config, write_env: writeEnv }),
  });
}

// Presets
export async function getPresets(): Promise<{
  success: boolean;
  presets: Array<{ name: string; created_at: string; modified_at: string }>;
  lastPreset: string | null;
}> {
  return fetchApi("/api/config/presets");
}

export async function getPreset(name: string): Promise<{
  success: boolean;
  preset: {
    name: string;
    created_at: string;
    modified_at: string;
    values: Record<string, string>;
    configuredSecrets: string[];
  };
}> {
  return fetchApi(`/api/config/presets/${encodeURIComponent(name)}`);
}

export async function savePreset(
  name: string,
  values: Record<string, string>
): Promise<{ success: boolean }> {
  return fetchApi("/api/config/presets", {
    method: "POST",
    body: JSON.stringify({ name, values }),
  });
}

export async function deletePreset(name: string): Promise<{ success: boolean }> {
  return fetchApi(`/api/config/presets/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

// Bot Control
export async function getBotStatus(): Promise<{
  success: boolean;
  status: "stopped" | "starting" | "running" | "stopping" | "error";
  pid?: number;
  started_at?: string;
  error?: string;
}> {
  return fetchApi("/api/bot/status");
}

export async function startBot(options?: {
  preventSleep?: boolean;
  writeEnv?: boolean;
  config?: Record<string, string>;
}): Promise<{
  success: boolean;
  status?: string;
  pid?: number;
  error?: string;
}> {
  return fetchApi("/api/bot/start", {
    method: "POST",
    body: JSON.stringify({
      prevent_sleep: options?.preventSleep ?? false,
      write_env: options?.writeEnv ?? false,
      config: options?.config,
    }),
  });
}

export async function stopBot(): Promise<{
  success: boolean;
  status?: string;
  error?: string;
}> {
  return fetchApi("/api/bot/stop", {
    method: "POST",
  });
}

// Bot Tracked Positions
export async function getTrackedPositions(): Promise<{
  success: boolean;
  positions: Array<{
    msg_id: number;
    mt5_ticket: number;
    symbol: string;
    role: string;
    order_type: string;
    entry_price: number | null;
    stop_loss: number | null;
    lot_size: number | null;
    status: string;
    opened_at: string;
  }>;
  total: number;
  open: number;
  closed: number;
}> {
  return fetchApi("/api/bot/positions");
}

export async function clearTrackedPositions(): Promise<{ success: boolean }> {
  return fetchApi("/api/bot/positions", { method: "DELETE" });
}

// Analysis
export async function getAnalysisSummary(): Promise<{
  success: boolean;
  summary: {
    total_signals: number;
    tp2_hit: number;
    tp1_hit: number;
    sl_hit: number;
    tp_unnumbered: number;
    win_rate: number;
    tp1_to_tp2_conversion: number;
    date_range: { start: string; end: string } | null;
    avg_time_to_tp1_minutes?: number;
    avg_time_to_tp2_minutes?: number;
  };
}> {
  return fetchApi("/api/analysis/summary");
}

export async function runAnalysis(
  action: "fetch" | "report",
  options?: { total?: number; batch?: number; delay?: number }
): Promise<{
  success: boolean;
  output?: string;
  error?: string;
}> {
  return fetchApi("/api/analysis/run", {
    method: "POST",
    body: JSON.stringify({ action, ...options }),
  });
}

// Telegram Channels
export interface TelegramChannel {
  id: string;
  name: string;
  username?: string;
  type: "channel" | "group";
}

export async function getTelegramChannels(
  apiId: string,
  apiHash: string
): Promise<{ channels: TelegramChannel[] }> {
  return fetchApi(`/api/telegram/channels?api_id=${apiId}&api_hash=${apiHash}`);
}

// System Prompts
export async function getSystemPrompts(): Promise<{
  success: boolean;
  system_prompt: string;
  correction_system_prompt: string;
  default_system_prompt: string;
  default_correction_system_prompt: string;
  is_custom_system_prompt: boolean;
  is_custom_correction_prompt: boolean;
}> {
  return fetchApi("/api/prompts");
}

export async function saveSystemPrompts(prompts: {
  system_prompt?: string;
  correction_system_prompt?: string;
}): Promise<{ success: boolean }> {
  return fetchApi("/api/prompts", {
    method: "PUT",
    body: JSON.stringify(prompts),
  });
}

export async function resetSystemPrompts(): Promise<{ success: boolean }> {
  return fetchApi("/api/prompts", {
    method: "DELETE",
  });
}
