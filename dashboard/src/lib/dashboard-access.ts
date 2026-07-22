import { ApiError, apiErrorFromResponse } from "./api-error";

type ProvisioningIdentity = {
  accessToken: string;
  user: { id: string; email: string };
};

export type ProvisionedDashboardSession = {
  active_account_id: string | null;
  setup_complete?: boolean;
};

function backendApiUrl() {
  return process.env.NEXT_PUBLIC_API_URL || "https://api.kiaparsaprintingmoneymachine.cloud";
}

export async function provisionDashboardAccess(
  authResponse: ProvisioningIdentity,
): Promise<ProvisionedDashboardSession> {
  const proxySecret = process.env.DASHBOARD_PROXY_SECRET?.trim();
  if (!proxySecret) {
    throw new ApiError("Dashboard provisioning is not configured.", 500, "proxy_not_configured");
  }

  const headers = new Headers({
    accept: "application/json",
    authorization: `Bearer ${authResponse.accessToken}`,
    "x-dashboard-proxy-auth": proxySecret,
    "x-workos-user-id": authResponse.user.id,
    "x-workos-user-email": authResponse.user.email,
  });

  let response = await fetch(`${backendApiUrl()}/api/access/session`, {
    method: "POST",
    headers,
    cache: "no-store",
  });

  // Preserve sign-in during the brief rolling-deploy window where the dashboard
  // may be newer than the API. The legacy endpoint provisions on read.
  if (response.status === 404 || response.status === 405) {
    response = await fetch(`${backendApiUrl()}/api/access/me`, {
      method: "GET",
      headers,
      cache: "no-store",
    });
  }

  if (!response.ok) throw await apiErrorFromResponse(response);
  return response.json();
}

export function dashboardNeedsSetup(session: ProvisionedDashboardSession): boolean {
  return !session.active_account_id || !session.setup_complete;
}
