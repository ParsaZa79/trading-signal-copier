const PUBLIC_PREFIXES = ["/sign-in", "/sign-up", "/api/auth"];

export function isPublicAuthRoute(pathname: string) {
  return PUBLIC_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function hasApiProxyIdentity(
  mode: "better-auth" | "clerk" | "local",
  authorization: string | null,
  clerkUserId: string | null | undefined,
) {
  if (mode === "better-auth") return /^Bearer\s+\S+$/.test(authorization ?? "");
  return mode === "clerk" ? Boolean(clerkUserId) : false;
}

export type RouteDecision =
  | { action: "next" }
  | { action: "redirect"; location: string };

export function betterAuthRouteDecision(url: URL, hasSessionCookie: boolean): RouteDecision {
  if (isPublicAuthRoute(url.pathname) || hasSessionCookie) return { action: "next" };
  const signIn = new URL("/sign-in", url.origin);
  signIn.searchParams.set("callbackURL", `${url.pathname}${url.search}`);
  return { action: "redirect", location: signIn.toString() };
}
