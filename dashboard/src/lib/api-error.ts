export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export async function apiErrorFromResponse(response: Response): Promise<ApiError> {
  const payload = await response.json().catch(() => null);
  const detail = payload && typeof payload === "object" ? payload.detail : null;
  const code =
    detail && typeof detail === "object" && typeof detail.code === "string"
      ? detail.code
      : null;
  const message =
    typeof detail === "string"
      ? detail
      : detail && typeof detail === "object" && typeof detail.message === "string"
        ? detail.message
        : `HTTP ${response.status}`;

  return new ApiError(message, response.status, code);
}

export function dashboardAccessMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Authentication succeeded, but dashboard setup could not be completed. Please try again.";
  }
  if (error.code === "access_disabled") {
    return "This dashboard account has been disabled. Ask an owner to restore access.";
  }
  return "Authentication succeeded, but dashboard setup is temporarily unavailable. Please try again.";
}
