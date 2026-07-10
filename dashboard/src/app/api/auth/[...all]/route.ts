import type { NextRequest } from "next/server";
import { GET as legacyGet, POST as legacyPost } from "../../[...path]/route";
import { getAuth, handleBetterAuthRequest } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    all: string[];
  }>;
};

function legacyContext(context: RouteContext) {
  return {
    params: context.params.then(({ all }) => ({ path: ["auth", ...all] })),
  };
}

export async function GET(request: NextRequest, context: RouteContext) {
  return handleBetterAuthRequest(request, getAuth, () =>
    legacyGet(request, legacyContext(context)),
  );
}

export async function POST(request: NextRequest, context: RouteContext) {
  return handleBetterAuthRequest(request, getAuth, () =>
    legacyPost(request, legacyContext(context)),
  );
}
