type AuthResult = {
  data?: unknown;
  error?: {
    code?: string;
    message?: string;
    status?: number;
    statusText?: string;
  } | null;
};
type EmailSignInClient = {
  signIn: {
    email(input: { email: string; password: string }, options: { headers: Record<string, string> }): Promise<AuthResult>;
  };
};
type PasswordResetClient = {
  requestPasswordReset(
    input: { email: string; redirectTo: string },
    options: { headers: Record<string, string> },
  ): Promise<AuthResult>;
};
type ResetPasswordClient = {
  resetPassword(input: { token: string; newPassword: string }): Promise<AuthResult>;
};

export function authCaptchaHeaders(token: string) {
  return { "x-captcha-response": token };
}

export async function signInWithPassword(
  client: EmailSignInClient,
  email: string,
  password: string,
  captchaToken: string,
) {
  const result = await client.signIn.email(
    { email: email.trim(), password },
    { headers: authCaptchaHeaders(captchaToken) },
  );
  if (!result.error) return { ok: true as const };
  if (result.error.code === "EMAIL_NOT_VERIFIED") {
    return {
      ok: false as const,
      emailVerificationRequired: true as const,
      message: "Verify your email before signing in.",
    };
  }
  return {
    ok: false as const,
    message: "Unable to sign in. Check your details and try again.",
  };
}

export async function requestPasswordReset(
  client: PasswordResetClient,
  email: string,
  redirectTo: string,
  captchaToken: string,
) {
  const result = await client.requestPasswordReset(
    { email: email.trim(), redirectTo },
    { headers: authCaptchaHeaders(captchaToken) },
  );
  if (result.error?.status === 429) {
    return {
      ok: false as const,
      message: "Too many reset requests. Please wait before trying again.",
    };
  }
  return {
    ok: true as const,
    message: "If an account exists, a reset link has been sent.",
  };
}

export async function resetPassword(client: ResetPasswordClient, token: string, newPassword: string) {
  const result = await client.resetPassword({ token, newPassword });
  return result.error ? { ok: false as const } : { ok: true as const };
}

export function safeAuthCallback(value: string | null | undefined) {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/";
}

export function signupAvailability(openSignup: boolean) {
  return openSignup
    ? { showForm: true as const, message: "Create account" }
    : { showForm: false as const, message: "Account registration is closed" };
}
