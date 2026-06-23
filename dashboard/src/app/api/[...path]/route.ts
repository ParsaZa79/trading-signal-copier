import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";

const BACKEND_API_URL =
  process.env.NEXT_PUBLIC_API_URL || "https://api.kiaparsaprintingmoneymachine.cloud";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

const FORWARDED_RESPONSE_HEADERS = ["content-type", "cache-control"];
const FORWARDED_REQUEST_HEADERS = ["accept", "content-type", "x-account-id"];

async function proxyApiRequest(request: NextRequest, context: RouteContext) {
  const { getToken } = await auth();
  const token = await getToken();
  if (!token) {
    return Response.json({ detail: "Authentication required" }, { status: 401 });
  }

  const { path } = await context.params;
  const targetUrl = new URL(`/api/${path.join("/")}`, BACKEND_API_URL);
  targetUrl.search = request.nextUrl.search;

  const headers = new Headers();
  for (const header of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(header);
    if (value) headers.set(header, value);
  }
  headers.set("authorization", `Bearer ${token}`);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });

  const responseHeaders = new Headers();
  for (const header of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(header);
    if (value) responseHeaders.set(header, value);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyApiRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyApiRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyApiRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyApiRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyApiRequest(request, context);
}
