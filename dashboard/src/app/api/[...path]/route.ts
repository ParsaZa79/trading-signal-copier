import { auth, currentUser } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";
import { AUTH_MODE } from "@/lib/auth-mode";
import { hasApiProxyIdentity } from "@/lib/proxy-policy";

const BACKEND_API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.kiaparsaprintingmoneymachine.cloud";
type RouteContext = { params: Promise<{ path: string[] }> };
const FORWARDED_RESPONSE_HEADERS = ["content-type"];
const FORWARDED_REQUEST_HEADERS = ["accept", "content-type", "x-account-id"];

async function proxyApiRequest(request: NextRequest, context: RouteContext) {
  const betterAuthToken = request.headers.get("authorization");
  const clerkAuth = AUTH_MODE === "clerk" ? await auth() : null;
  const sessionId = clerkAuth?.sessionId;
  const userId = clerkAuth?.userId;
  if (!hasApiProxyIdentity(AUTH_MODE, betterAuthToken, userId)) {
    return privateJson({ detail: "Authentication required" }, 401);
  }
  const proxySecret = process.env.DASHBOARD_PROXY_SECRET;
  if (!proxySecret) return privateJson({ detail: "Dashboard proxy is not configured" }, 500);
  const clerkUser = AUTH_MODE === "clerk" ? await currentUser() : null;
  const email = clerkUser?.primaryEmailAddress?.emailAddress || clerkUser?.emailAddresses?.find((item) => Boolean(item.emailAddress))?.emailAddress;
  const { path } = await context.params;
  const targetUrl = new URL(`/api/${path.join("/")}`, BACKEND_API_URL);
  targetUrl.search = request.nextUrl.search;
  const headers = new Headers();
  for (const header of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(header);
    if (value) headers.set(header, value);
  }
  headers.set("x-dashboard-proxy-auth", proxySecret);
  if (betterAuthToken) headers.set("authorization", betterAuthToken);
  if (userId) headers.set("x-clerk-user-id", userId);
  if (email) headers.set("x-clerk-user-email", email);
  if (sessionId) headers.set("x-clerk-session-id", sessionId);
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });
  const responseHeaders = new Headers({ "cache-control": "private, no-store", pragma: "no-cache" });
  for (const header of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(header);
    if (value) responseHeaders.set(header, value);
  }
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: responseHeaders });
}

function privateJson(body: object, status: number) {
  return Response.json(body, { status, headers: { "cache-control": "private, no-store", pragma: "no-cache" } });
}

export async function GET(request: NextRequest, context: RouteContext) { return proxyApiRequest(request, context); }
export async function POST(request: NextRequest, context: RouteContext) { return proxyApiRequest(request, context); }
export async function PUT(request: NextRequest, context: RouteContext) { return proxyApiRequest(request, context); }
export async function PATCH(request: NextRequest, context: RouteContext) { return proxyApiRequest(request, context); }
export async function DELETE(request: NextRequest, context: RouteContext) { return proxyApiRequest(request, context); }
