export async function signOut() {}

export async function withAuth() {
  return { user: null, accessToken: null };
}

export function authkitProxy() {
  return () => undefined;
}

export async function getSignInUrl() {
  return "http://localhost:3000/sign-in";
}

export function handleAuth() {
  return () => undefined;
}

export function AuthKitProvider({ children }: { children: unknown }) {
  return children;
}
