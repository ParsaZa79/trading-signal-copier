export function useAuth() {
  return { user: null, loading: false };
}

export function useAccessToken() {
  return {
    accessToken: null,
    loading: false,
    error: null,
    getAccessToken: async () => null,
  };
}

export function AuthKitProvider({ children }: { children: unknown }) {
  return children;
}
