export interface DashboardUser {
  id: string;
  email: string;
  role?: "owner" | "admin" | "trader" | "viewer";
  status?: "active" | "disabled" | "pending";
  auth_provider?: "local" | "workos";
  active_account_id?: string | null;
  created_at?: string;
}

export interface DashboardAccount {
  id: string;
  name: string;
  user_id: string;
  setup_complete?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AuthSession {
  token: string;
  user: DashboardUser;
  accounts: DashboardAccount[];
  activeAccountId: string | null;
  setupComplete: boolean;
}

const ACTIVE_ACCOUNT_KEY = "signal_copier_active_account";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getActiveAccountId(): string | null {
  if (!canUseStorage()) return null;
  return window.localStorage.getItem(ACTIVE_ACCOUNT_KEY);
}

export function setActiveAccountId(accountId: string | null) {
  if (!canUseStorage()) return;
  if (accountId) {
    window.localStorage.setItem(ACTIVE_ACCOUNT_KEY, accountId);
  } else {
    window.localStorage.removeItem(ACTIVE_ACCOUNT_KEY);
  }
}

export function buildAuthenticatedWsUrl(baseUrl: string, token: string, accountId: string) {
  const url = new URL(baseUrl);
  url.searchParams.set("token", token);
  url.searchParams.set("account_id", accountId);
  return url.toString();
}
