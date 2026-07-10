import { betterAuth, type BetterAuthOptions } from "better-auth";
import { admin as adminPlugin, captcha, jwt } from "better-auth/plugins";
import { Pool, type PoolConfig } from "pg";
import {
  createSmtpEmailSender,
  passwordResetEmail,
  verificationEmail,
  type AuthEmailSender,
  type SmtpSettings,
} from "./auth/email";
import {
  ADMIN_ROLES,
  DEFAULT_ROLE,
  authAccessControl,
  authRoles,
  isAuthRole,
} from "./auth/permissions";

type Environment = Readonly<Record<string, string | undefined>>;

export const AUTH_JWT_EXPIRATION = "5m";

const AUTH_SCHEMA = "auth";
const REQUIRED_ENV = [
  "BETTER_AUTH_SECRET",
  "BETTER_AUTH_URL",
  "BETTER_AUTH_DATABASE_URL",
  "BETTER_AUTH_JWT_AUDIENCE",
  "SMTP_HOST",
  "SMTP_PORT",
  "SMTP_USER",
  "SMTP_PASSWORD",
  "SMTP_FROM",
] as const;

export interface BetterAuthSettings {
  baseURL: string;
  captchaAllowedHostnames: string[];
  databaseURL: string;
  jwtAudience: string;
  openSignupEnabled: boolean;
  secret: string;
  secureCookies: boolean;
  smtp: SmtpSettings;
  trustedOrigins: string[];
  turnstileSecretKey?: string;
}

export interface BetterAuthServer {
  handler(request: Request): Promise<Response>;
}

export interface BetterAuthDependencies {
  createAuth(options: BetterAuthOptions): BetterAuthServer;
  createEmailSender(settings: SmtpSettings): AuthEmailSender;
  createPool(settings: BetterAuthSettings): Pool;
}

export class AuthConfigurationError extends Error {
  readonly variables: readonly string[];

  constructor(variables: readonly string[]) {
    const uniqueVariables = [...new Set(variables)].sort();
    super(`Better Auth configuration is invalid: ${uniqueVariables.join(", ")}`);
    this.name = "AuthConfigurationError";
    this.variables = uniqueVariables;
  }
}

export function resolveBetterAuthSettings(
  environment: Environment,
): BetterAuthSettings | null {
  const strategyLabFlag =
    environment.STRATEGY_LAB_ENABLED ??
    environment.NEXT_PUBLIC_STRATEGY_LAB_ENABLED;

  if (
    !isExplicitlyEnabled(environment.BETTER_AUTH_ENABLED) ||
    !isExplicitlyEnabled(strategyLabFlag)
  ) {
    return null;
  }

  const openSignupEnabled = isExplicitlyEnabled(
    environment.OPEN_SIGNUP_ENABLED,
  );
  const invalidVariables: string[] = REQUIRED_ENV.filter(
    (name) => !environment[name]?.trim(),
  );
  const turnstileSecretKey = environment.TURNSTILE_SECRET_KEY?.trim() || undefined;

  if (!turnstileSecretKey) {
    invalidVariables.push("TURNSTILE_SECRET_KEY");
  }
  const secret = environment.BETTER_AUTH_SECRET ?? "";
  if (secret.length < 32 || secret.trim() !== secret) {
    invalidVariables.push("BETTER_AUTH_SECRET");
  }

  if (invalidVariables.length > 0) {
    throw new AuthConfigurationError(invalidVariables);
  }

  const baseURL = parseOrigin(
    environment.BETTER_AUTH_URL!,
    "BETTER_AUTH_URL",
    environment.NODE_ENV === "production",
  );
  const jwtAudience = parseOrigin(
    environment.BETTER_AUTH_JWT_AUDIENCE!,
    "BETTER_AUTH_JWT_AUDIENCE",
    environment.NODE_ENV === "production",
  );
  validatePostgresURL(environment.BETTER_AUTH_DATABASE_URL!);

  const smtpPort = parsePort(environment.SMTP_PORT!);
  const smtpSecure = parseOptionalBoolean(
    environment.SMTP_SECURE,
    "SMTP_SECURE",
  );
  for (const name of ["SMTP_HOST", "SMTP_USER", "SMTP_FROM"] as const) {
    rejectHeaderCharacters(environment[name]!, name);
  }

  const trustedOrigins = new Set([baseURL]);
  for (const origin of (environment.BETTER_AUTH_TRUSTED_ORIGINS ?? "").split(",")) {
    if (origin.trim()) {
      trustedOrigins.add(
        parseOrigin(
          origin,
          "BETTER_AUTH_TRUSTED_ORIGINS",
          environment.NODE_ENV === "production",
        ),
      );
    }
  }

  return {
    baseURL,
    captchaAllowedHostnames: [new URL(baseURL).hostname],
    databaseURL: environment.BETTER_AUTH_DATABASE_URL!.trim(),
    jwtAudience,
    openSignupEnabled,
    secret,
    secureCookies:
      new URL(baseURL).protocol === "https:" || environment.NODE_ENV === "production",
    smtp: {
      from: environment.SMTP_FROM!.trim(),
      host: environment.SMTP_HOST!.trim(),
      password: environment.SMTP_PASSWORD!,
      port: smtpPort,
      secure: smtpSecure,
      user: environment.SMTP_USER!.trim(),
    },
    trustedOrigins: [...trustedOrigins],
    turnstileSecretKey,
  };
}

export function buildBetterAuthOptions(
  settings: BetterAuthSettings,
  database: Pool,
  sendEmail: AuthEmailSender,
): BetterAuthOptions {
  const plugins: NonNullable<BetterAuthOptions["plugins"]> = [
    adminPlugin({
      ac: authAccessControl,
      roles: authRoles,
      defaultRole: DEFAULT_ROLE,
      adminRoles: [...ADMIN_ROLES],
    }),
    jwt({
      disableSettingJwtHeader: true,
      jwks: {
        keyPairConfig: {
          alg: "RS256",
          modulusLength: 2048,
        },
        rotationInterval: 60 * 60 * 24 * 30,
        gracePeriod: 60 * 60 * 24,
      },
      jwt: {
        issuer: settings.baseURL,
        audience: settings.jwtAudience,
        expirationTime: AUTH_JWT_EXPIRATION,
        getSubject: getJwtSubject,
        definePayload: createJwtPayload,
      },
    }),
  ];

  if (settings.turnstileSecretKey) {
    plugins.push(
      captcha({
        provider: "cloudflare-turnstile",
        secretKey: settings.turnstileSecretKey,
        allowedHostnames: settings.captchaAllowedHostnames,
      }),
    );
  }

  return {
    appName: "Strategy Lab",
    baseURL: settings.baseURL,
    basePath: "/api/auth",
    secret: settings.secret,
    trustedOrigins: settings.trustedOrigins,
    database,
    emailAndPassword: {
      enabled: true,
      disableSignUp: !settings.openSignupEnabled,
      requireEmailVerification: true,
      minPasswordLength: 12,
      maxPasswordLength: 128,
      autoSignIn: false,
      revokeSessionsOnPasswordReset: true,
      resetPasswordTokenExpiresIn: 60 * 60,
      sendResetPassword: async ({ user, url }) => {
        sendEmailWithoutWaiting(sendEmail, passwordResetEmail(user.email, url));
      },
      customSyntheticUser: ({ coreFields, additionalFields, id }) => ({
        ...coreFields,
        role: DEFAULT_ROLE,
        banned: false,
        banReason: null,
        banExpires: null,
        ...additionalFields,
        id,
      }),
    },
    emailVerification: {
      sendVerificationEmail: async ({ user, url }) => {
        sendEmailWithoutWaiting(sendEmail, verificationEmail(user.email, url));
      },
      sendOnSignUp: true,
      sendOnSignIn: true,
      autoSignInAfterVerification: false,
      expiresIn: 60 * 60,
    },
    rateLimit: {
      enabled: true,
      storage: "database",
      window: 60,
      max: 100,
      customRules: {
        "/sign-in/email": { window: 60, max: 5 },
        "/sign-up/email": { window: 60 * 60, max: 3 },
        "/request-password-reset": { window: 60 * 60, max: 3 },
        "/send-verification-email": { window: 60 * 60, max: 3 },
      },
    },
    advanced: {
      useSecureCookies: settings.secureCookies,
      defaultCookieAttributes: {
        httpOnly: true,
        secure: settings.secureCookies,
        sameSite: "lax",
        path: "/",
      },
    },
    plugins,
  };
}

export function createJwtPayload({
  user,
}: {
  user: {
    email: string;
    emailVerified: boolean;
    role?: unknown;
  };
}) {
  return {
    email: user.email,
    email_verified: user.emailVerified,
    role: isAuthRole(user.role) ? user.role : "viewer",
  };
}

export function getJwtSubject({ user }: { user: { id: string } }) {
  return user.id;
}

const defaultDependencies: BetterAuthDependencies = {
  createAuth: (options) => betterAuth(options),
  createEmailSender: createSmtpEmailSender,
  createPool: createPostgresPool,
};

export function createBetterAuthFromEnv(
  environment: Environment,
  dependencies: BetterAuthDependencies = defaultDependencies,
): BetterAuthServer | null {
  const settings = resolveBetterAuthSettings(environment);
  if (!settings) {
    return null;
  }

  const pool = dependencies.createPool(settings);
  try {
    const sendEmail = dependencies.createEmailSender(settings.smtp);
    return dependencies.createAuth(
      buildBetterAuthOptions(settings, pool, sendEmail),
    );
  } catch (error) {
    void pool.end().catch(() => undefined);
    throw error;
  }
}

const authGlobal = globalThis as typeof globalThis & {
  strategyLabBetterAuth?: BetterAuthServer;
};

// The named export keeps the pinned Better Auth CLI discoverable when operators
// intentionally opt into CLI mode with the complete activation environment. It
// remains null and allocates no runtime resources during normal imports/builds.
export const auth = isExplicitlyEnabled(process.env.BETTER_AUTH_CLI)
  ? createBetterAuthFromEnv(process.env)
  : null;

export function getAuth(): BetterAuthServer | null {
  if (authGlobal.strategyLabBetterAuth) {
    return authGlobal.strategyLabBetterAuth;
  }

  const runtimeAuth = auth ?? createBetterAuthFromEnv(process.env);
  if (runtimeAuth) {
    authGlobal.strategyLabBetterAuth = runtimeAuth;
  }
  return runtimeAuth;
}

export async function handleBetterAuthRequest(
  request: Request,
  resolveAuth: () => BetterAuthServer | null = getAuth,
  disabledHandler: (request: Request) => Response | Promise<Response> = () =>
    authErrorResponse(404, "Not found"),
) {
  let auth: BetterAuthServer | null;
  try {
    auth = resolveAuth();
  } catch {
    if (process.env.NODE_ENV !== "test") {
      console.error("[auth] Better Auth initialization failed");
    }
    return authErrorResponse(503, "Authentication service unavailable");
  }

  if (!auth) {
    return disabledHandler(request);
  }
  return auth.handler(request);
}

function createPoolConfig(settings: BetterAuthSettings): PoolConfig {
  return {
    connectionString: settings.databaseURL,
    options: `-c search_path=${AUTH_SCHEMA}`,
    application_name: "trading-dashboard-better-auth",
    max: 10,
    connectionTimeoutMillis: 5_000,
    idleTimeoutMillis: 30_000,
    allowExitOnIdle: true,
  };
}

function createPostgresPool(settings: BetterAuthSettings) {
  const pool = new Pool(createPoolConfig(settings));
  pool.on("error", () => {
    console.error("[auth] Better Auth PostgreSQL pool error");
  });
  return pool;
}

function isExplicitlyEnabled(value: string | undefined) {
  return value?.trim().toLowerCase() === "true";
}

function parseOrigin(value: string, variable: string, requireHttps = false) {
  try {
    const url = new URL(value.trim());
    if (
      !["http:", "https:"].includes(url.protocol) ||
      (requireHttps && url.protocol !== "https:") ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    ) {
      throw new Error("invalid origin");
    }
    return url.origin;
  } catch {
    throw new AuthConfigurationError([variable]);
  }
}

function validatePostgresURL(value: string) {
  try {
    const url = new URL(value.trim());
    if (!["postgres:", "postgresql:"].includes(url.protocol)) {
      throw new Error("invalid protocol");
    }
  } catch {
    throw new AuthConfigurationError(["BETTER_AUTH_DATABASE_URL"]);
  }
}

function parsePort(value: string) {
  const port = Number(value);
  if (!/^\d+$/.test(value) || !Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new AuthConfigurationError(["SMTP_PORT"]);
  }
  return port;
}

function parseOptionalBoolean(value: string | undefined, variable: string) {
  if (value === undefined || value.trim() === "") {
    return false;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "true") return true;
  if (normalized === "false") return false;
  throw new AuthConfigurationError([variable]);
}

function rejectHeaderCharacters(value: string, variable: string) {
  if (/[\r\n]/.test(value)) {
    throw new AuthConfigurationError([variable]);
  }
}

function sendEmailWithoutWaiting(
  sendEmail: AuthEmailSender,
  message: Parameters<AuthEmailSender>[0],
) {
  void sendEmail(message).catch(() => {
    console.error("[auth] Auth email delivery failed");
  });
}

function authErrorResponse(status: number, error: string) {
  return Response.json(
    { error },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
