import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { getSessionCookie } from "better-auth/cookies";
import { NextRequest, NextResponse } from "next/server";
import { AUTH_MODE } from "./lib/auth-mode";
import { betterAuthRouteDecision } from "./lib/proxy-policy";

const isPublicClerkRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"]);

const clerkProxy = clerkMiddleware(
  async (auth, req) => {
    if (!isPublicClerkRoute(req)) await auth.protect();
  },
  { signInUrl: "/sign-in", signUpUrl: "/sign-up" },
);

function betterAuthProxy(request: NextRequest) {
  const decision = betterAuthRouteDecision(
    request.nextUrl,
    Boolean(getSessionCookie(request)),
  );
  return decision.action === "next"
    ? NextResponse.next()
    : NextResponse.redirect(decision.location);
}

export default AUTH_MODE === "better-auth"
  ? betterAuthProxy
  : AUTH_MODE === "clerk"
    ? clerkProxy
    : function legacyLocalProxy() {
        return NextResponse.next();
      };

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
  ],
};
