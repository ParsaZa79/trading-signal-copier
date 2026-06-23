export interface DashboardUser {
  id: string;
  email: string;
  role?: "owner" | "admin" | "trader" | "viewer";
  status?: "active" | "disabled" | "pending";
  auth_provider?: "local" | "clerk";
  active_account_id?: string | null;
  created_at?: string;
}

export interface DashboardAccount {
  id: string;
  name: string;
  user_id: string;
  created_at?: string;
  updated_at?: string;
}

export interface AuthSession {
  token: string;
  user: DashboardUser;
  accounts: DashboardAccount[];
  activeAccountId: string;
}

const STORAGE_KEY = "signal_copier_auth";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getStoredSession(): AuthSession | null {
  if (!canUseStorage()) return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed.token || !parsed.activeAccountId) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function storeSession(session: AuthSession) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event("signal-copier-auth-changed"));
}

export function clearStoredSession() {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event("signal-copier-auth-changed"));
}

export function getAuthToken(): string | null {
  return getStoredSession()?.token ?? null;
}

export function getActiveAccountId(): string | null {
  return getStoredSession()?.activeAccountId ?? null;
}

export function setActiveAccountId(accountId: string) {
  const session = getStoredSession();
  if (!session) return;
  storeSession({ ...session, activeAccountId: accountId });
}

export function buildAuthenticatedWsUrl(baseUrl: string, token: string, accountId: string) {
  const url = new URL(baseUrl);
  url.searchParams.set("token", token);
  url.searchParams.set("account_id", accountId);
  return url.toString();
}
