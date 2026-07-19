import type { BetterAuthOptions } from "better-auth";
import type { Pool } from "pg";
import { describe, expect, it, vi } from "vitest";
import {
  AUTH_JWT_EXPIRATION,
  AuthConfigurationError,
  buildBetterAuthOptions,
  createBetterAuthFromEnv,
  createJwtPayload,
  getJwtSubject,
  handleBetterAuthRequest,
  resolveBetterAuthSettings,
} from "../auth";
import {
  ADMIN_ROLES,
  AUTH_ROLES,
  DEFAULT_ROLE,
  authRoles,
} from "./permissions";

const COMPLETE_ENV = {
  NODE_ENV: "test",
  BETTER_AUTH_ENABLED: "true",
  STRATEGY_LAB_ENABLED: "true",
  OPEN_SIGNUP_ENABLED: "false",
  BETTER_AUTH_SECRET: "s".repeat(32),
  BETTER_AUTH_URL: "https://dashboard.example.test",
  BETTER_AUTH_DATABASE_URL: "postgresql://database.example.test/trading",
  BETTER_AUTH_JWT_AUDIENCE: "https://api.example.test",
  SMTP_HOST: "mail.example.test",
  SMTP_PORT: "587",
  SMTP_USER: "auth-mailer",
  SMTP_PASSWORD: "p".repeat(32),
  SMTP_FROM: "no-reply@example.test",
  TURNSTILE_SECRET_KEY: "test-turnstile-secret",
} satisfies NodeJS.ProcessEnv;

function makeDependencies() {
  const pool = {} as Pool;
  const sendEmail = vi.fn(async () => undefined);
  const serverAuth = {
    handler: vi.fn(async () => new Response(null, { status: 204 })),
  };

  return {
    pool,
    sendEmail,
    serverAuth,
    dependencies: {
      createPool: vi.fn(() => pool),
      createEmailSender: vi.fn(() => sendEmail),
      createAuth: vi.fn(() => serverAuth),
    },
  };
}

function getPluginOptions(options: BetterAuthOptions, id: string) {
  const plugin = options.plugins?.find((candidate) => candidate.id === id);
  expect(plugin, `missing ${id} plugin`).toBeDefined();
  return (plugin as { options?: Record<string, unknown> }).options;
}

describe("Better Auth feature gates", () => {
  it("is inert with absent or disabled feature flags", () => {
    const { dependencies } = makeDependencies();

    expect(resolveBetterAuthSettings({})).toBeNull();
    expect(
      resolveBetterAuthSettings({
        ...COMPLETE_ENV,
        BETTER_AUTH_ENABLED: "false",
      }),
    ).toBeNull();
    expect(
      resolveBetterAuthSettings({
        ...COMPLETE_ENV,
        STRATEGY_LAB_ENABLED: "false",
      }),
    ).toBeNull();
    expect(createBetterAuthFromEnv({}, dependencies)).toBeNull();
    expect(dependencies.createPool).not.toHaveBeenCalled();
    expect(dependencies.createEmailSender).not.toHaveBeenCalled();
    expect(dependencies.createAuth).not.toHaveBeenCalled();
  });

  it("requires both private server flags and ignores the public UI flag", () => {
    expect(
      resolveBetterAuthSettings({
        ...COMPLETE_ENV,
        STRATEGY_LAB_ENABLED: undefined,
        NEXT_PUBLIC_STRATEGY_LAB_ENABLED: "true",
      }),
    ).toBeNull();
    expect(
      resolveBetterAuthSettings({
        ...COMPLETE_ENV,
        STRATEGY_LAB_ENABLED: "false",
        NEXT_PUBLIC_STRATEGY_LAB_ENABLED: "true",
      }),
    ).toBeNull();
    expect(
      resolveBetterAuthSettings({
        ...COMPLETE_ENV,
        STRATEGY_LAB_ENABLED: "true",
        NEXT_PUBLIC_STRATEGY_LAB_ENABLED: "false",
      }),
    ).toMatchObject({ baseURL: COMPLETE_ENV.BETTER_AUTH_URL });
  });

  it("fails closed without activation configuration and never exposes values", () => {
    const incomplete = {
      NODE_ENV: "test",
      BETTER_AUTH_ENABLED: "true",
      STRATEGY_LAB_ENABLED: "true",
      BETTER_AUTH_SECRET: "do-not-echo-this-value",
    } satisfies NodeJS.ProcessEnv;

    let error: unknown;
    try {
      resolveBetterAuthSettings(incomplete);
    } catch (caught) {
      error = caught;
    }

    expect(error).toBeInstanceOf(AuthConfigurationError);
    expect(String(error)).toContain("BETTER_AUTH_DATABASE_URL");
    expect(String(error)).toContain("SMTP_HOST");
    expect(String(error)).not.toContain(incomplete.BETTER_AUTH_SECRET);
  });

  it("requires captcha whenever Better Auth is enabled", () => {
    expect(() =>
      resolveBetterAuthSettings({
        ...COMPLETE_ENV,
        TURNSTILE_SECRET_KEY: undefined,
      }),
    ).toThrow(/TURNSTILE_SECRET_KEY/);
  });

  it("rejects insecure production origins and padded secrets", () => {
    expect(() =>
      resolveBetterAuthSettings({
        ...COMPLETE_ENV,
        NODE_ENV: "production",
        BETTER_AUTH_URL: "http://dashboard.example.test",
      }),
    ).toThrow(/BETTER_AUTH_URL/);
    expect(() =>
      resolveBetterAuthSettings({
        ...COMPLETE_ENV,
        BETTER_AUTH_SECRET: ` ${"s".repeat(32)}`,
      }),
    ).toThrow(/BETTER_AUTH_SECRET/);
  });
});

describe("Better Auth server options", () => {
  it("configures verified email, secure cookies, JWT/JWKS, roles, and rate limits", () => {
    const settings = resolveBetterAuthSettings(COMPLETE_ENV);
    expect(settings).not.toBeNull();

    const sendEmail = vi.fn(async () => undefined);
    const options = buildBetterAuthOptions(settings!, {} as Pool, sendEmail);

    expect(options.emailAndPassword).toMatchObject({
      enabled: true,
      disableSignUp: true,
      requireEmailVerification: true,
      autoSignIn: false,
      revokeSessionsOnPasswordReset: true,
    });
    expect(options.emailVerification).toMatchObject({
      sendOnSignUp: true,
      sendOnSignIn: true,
      autoSignInAfterVerification: false,
    });
    expect(options.advanced).toMatchObject({
      useSecureCookies: true,
      defaultCookieAttributes: {
        httpOnly: true,
        secure: true,
        sameSite: "lax",
        path: "/",
      },
    });
    expect(options.rateLimit).toMatchObject({
      enabled: true,
      storage: "database",
      customRules: {
        "/sign-in/email": { window: 60, max: 5 },
        "/sign-up/email": { window: 3600, max: 3 },
        "/request-password-reset": { window: 3600, max: 3 },
      },
    });
    expect(options.logger).toEqual({ disabled: true });

    const adminOptions = getPluginOptions(options, "admin");
    expect(adminOptions).toMatchObject({
      defaultRole: DEFAULT_ROLE,
      adminRoles: ADMIN_ROLES,
    });

    const jwtPluginOptions = getPluginOptions(options, "jwt");
    expect(jwtPluginOptions).toMatchObject({ disableSettingJwtHeader: true });
    const jwtOptions = jwtPluginOptions?.jwt as {
      audience: string;
      expirationTime: string;
      getSubject: typeof getJwtSubject;
      issuer: string;
      definePayload: typeof createJwtPayload;
    };
    expect(jwtOptions).toMatchObject({
      issuer: COMPLETE_ENV.BETTER_AUTH_URL,
      audience: COMPLETE_ENV.BETTER_AUTH_JWT_AUDIENCE,
      expirationTime: AUTH_JWT_EXPIRATION,
      getSubject: getJwtSubject,
      definePayload: createJwtPayload,
    });
    expect(getPluginOptions(options, "captcha")).toMatchObject({
      provider: "cloudflare-turnstile",
      allowedHostnames: ["dashboard.example.test"],
    });

    const syntheticUser = options.emailAndPassword?.customSyntheticUser?.({
      coreFields: {
        name: "Test User",
        email: "user@example.test",
        emailVerified: false,
        image: null,
        createdAt: new Date(0),
        updatedAt: new Date(0),
      },
      additionalFields: {
        id: "attacker-id",
        name: "Attacker Name",
        email: "attacker@example.test",
        role: "owner",
        banned: true,
        banReason: "attacker-controlled",
        banExpires: new Date(1),
      },
      id: "generated-id",
    });
    expect(syntheticUser).toEqual(expect.objectContaining({
      id: "generated-id",
      name: "Test User",
      email: "user@example.test",
      role: DEFAULT_ROLE,
      banned: false,
      banReason: null,
      banExpires: null,
    }));
  });

  it("allows signup only when every gate is explicitly enabled", () => {
    const settings = resolveBetterAuthSettings({
      ...COMPLETE_ENV,
      OPEN_SIGNUP_ENABLED: "true",
    });
    const options = buildBetterAuthOptions(
      settings!,
      {} as Pool,
      vi.fn(async () => undefined),
    );

    expect(settings?.openSignupEnabled).toBe(true);
    expect(options.emailAndPassword?.disableSignUp).toBe(false);
  });

  it("awaits reset email delivery and logs only sanitized SMTP failure metadata", async () => {
    const smtpError = Object.assign(new Error("connection failed for private@example.test"), {
      code: "ETIMEDOUT",
      command: "CONN",
      responseCode: 421,
    });
    const sendEmail = vi.fn().mockRejectedValue(smtpError);
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const options = buildBetterAuthOptions(
      resolveBetterAuthSettings(COMPLETE_ENV)!,
      {} as Pool,
      sendEmail,
    );
    const sendResetPassword = options.emailAndPassword?.sendResetPassword as unknown as (
      input: {
        user: { email: string };
        url: string;
      },
    ) => Promise<void>;

    await expect(
      sendResetPassword({
        user: { email: "private@example.test" },
        url: "https://dashboard.example.test/reset?token=private-token",
      }),
    ).rejects.toBe(smtpError);

    expect(sendEmail).toHaveBeenCalledOnce();
    const logged = errorLog.mock.calls.flat().join(" ");
    expect(logged).toContain("password-reset");
    expect(logged).toContain("ETIMEDOUT");
    expect(logged).toContain("CONN");
    expect(logged).toContain("421");
    expect(logged).not.toContain("private@example.test");
    expect(logged).not.toContain("private-token");
    errorLog.mockRestore();
  });

  it("constructs runtime dependencies only after activation", () => {
    const { dependencies, pool, sendEmail, serverAuth } = makeDependencies();

    expect(
      createBetterAuthFromEnv(
        COMPLETE_ENV,
        dependencies,
      ),
    ).toBe(serverAuth);
    expect(dependencies.createPool).toHaveBeenCalledOnce();
    expect(dependencies.createEmailSender).toHaveBeenCalledOnce();
    expect(dependencies.createAuth).toHaveBeenCalledOnce();
    expect(dependencies.createAuth).toHaveBeenCalledWith(
      expect.objectContaining({ database: pool, secret: COMPLETE_ENV.BETTER_AUTH_SECRET }),
    );
    expect(dependencies.createEmailSender).toHaveReturnedWith(sendEmail);
  });

  it("persists exactly one known role and defaults new users to trader", async () => {
    const settings = resolveBetterAuthSettings(COMPLETE_ENV)!;
    const options = buildBetterAuthOptions(
      settings,
      {} as Pool,
      vi.fn(async () => undefined),
    );
    const createGuard = options.databaseHooks?.user?.create?.before;
    const updateGuard = options.databaseHooks?.user?.update?.before;
    expect(createGuard).toBeTypeOf("function");
    expect(updateGuard).toBeTypeOf("function");

    const defaulted = await createGuard?.(
      { id: "new-user", email: "new@example.test" } as never,
      null,
    );
    expect(defaulted).toEqual({
      data: expect.objectContaining({ role: DEFAULT_ROLE }),
    });

    for (const role of AUTH_ROLES) {
      await expect(
        createGuard?.({ id: "new-user", role } as never, null),
      ).resolves.toEqual({ data: expect.objectContaining({ role }) });
      await expect(updateGuard?.({ role } as never, null)).resolves.toEqual({
        data: expect.objectContaining({ role }),
      });
    }

    for (const hostileRole of [
      ["owner"],
      "owner,admin",
      " owner",
      "OWNER",
      "__proto__",
      "constructor",
      "toString",
      "",
      null,
    ]) {
      await expect(
        createGuard?.({ id: "new-user", role: hostileRole } as never, null),
      ).rejects.toThrow(/invalid role/i);
      await expect(
        updateGuard?.({ role: hostileRole } as never, null),
      ).rejects.toThrow(/invalid role/i);
    }
  });
});

describe("roles and JWT claims", () => {
  it("reserves every role and owner mutation for owners", () => {
    expect(Object.keys(authRoles)).toEqual(AUTH_ROLES);
    for (const permission of [
      "set-role",
      "ban",
      "impersonate",
      "delete",
      "set-password",
      "set-email",
      "update",
    ] as const) {
      expect(authRoles.owner.authorize({ user: [permission] }).success).toBe(true);
      expect(authRoles.admin.authorize({ user: [permission] }).success).toBe(false);
    }
    for (const permission of ["revoke", "delete", "list"] as const) {
      expect(authRoles.owner.authorize({ session: [permission] }).success).toBe(true);
      expect(authRoles.admin.authorize({ session: [permission] }).success).toBe(false);
    }
    expect(authRoles.admin.authorize({ user: ["create", "list", "get"] }).success).toBe(
      true,
    );
    expect(authRoles.trader.authorize({ user: ["list"] }).success).toBe(false);
    expect(authRoles.viewer.authorize({ user: ["list"] }).success).toBe(false);
  });

  it("allows only an owner role to perform protected role transitions", () => {
    for (const targetRole of AUTH_ROLES) {
      expect(
        authRoles.owner.authorize({ user: ["set-role"] }).success,
        `owner should be able to assign ${targetRole}`,
      ).toBe(true);
      expect(
        authRoles.admin.authorize({ user: ["set-role"] }).success,
        `admin must not be able to assign ${targetRole}`,
      ).toBe(false);
    }
  });

  it("uses the stable user id as subject and emits only required custom claims", () => {
    const user = {
      id: "stable-user-id",
      email: "verified@example.test",
      emailVerified: true,
      role: "admin",
    };

    expect(getJwtSubject({ user })).toBe(user.id);
    expect(createJwtPayload({ user })).toEqual({
      email: user.email,
      email_verified: true,
      role: "admin",
    });
    expect(createJwtPayload({ user: { ...user, role: "unexpected" } }).role).toBe(
      "viewer",
    );
    expect(createJwtPayload({ user: { ...user, role: "owner,admin" } }).role).toBe(
      "viewer",
    );
  });
});

describe("dormant catch-all handler", () => {
  it("delegates to the existing Clerk proxy while Better Auth is dormant", async () => {
    const legacyHandler = vi.fn(async () =>
      Response.json({ provider: "clerk" }, { status: 200 }),
    );

    const response = await handleBetterAuthRequest(
      new Request("https://dashboard.example.test/api/auth/me"),
      () => null,
      legacyHandler,
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ provider: "clerk" });
    expect(legacyHandler).toHaveBeenCalledOnce();
  });

  it("returns a non-cacheable 404 without an enabled auth instance", async () => {
    const resolveAuth = vi.fn(() => null);

    const response = await handleBetterAuthRequest(
      new Request("https://dashboard.example.test/api/auth/session"),
      resolveAuth,
    );

    expect(response.status).toBe(404);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("pragma")).toBe("no-cache");
    expect(resolveAuth).toHaveBeenCalledOnce();
  });

  it("overrides cacheable headers on every enabled Better Auth response", async () => {
    const response = await handleBetterAuthRequest(
      new Request("https://dashboard.example.test/api/auth/token"),
      () => ({
        handler: vi.fn(async () =>
          Response.json(
            { token: "short-lived-secret" },
            { headers: { "Cache-Control": "public, max-age=3600" } },
          ),
        ),
      }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("pragma")).toBe("no-cache");
  });

  it("returns a generic non-cacheable response when the auth handler fails", async () => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const response = await handleBetterAuthRequest(
      new Request("https://dashboard.example.test/api/auth/token"),
      () => ({
        handler: vi.fn(async () => {
          throw new Error("do-not-log-handler-secret");
        }),
      }),
    );

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: "Authentication service unavailable" });
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("pragma")).toBe("no-cache");
    expect(JSON.stringify(logged.mock.calls)).not.toContain("do-not-log-handler-secret");
    logged.mockRestore();
  });

  it("returns a generic 503 for invalid enabled configuration", async () => {
    const response = await handleBetterAuthRequest(
      new Request("https://dashboard.example.test/api/auth/session"),
      () => {
        throw new AuthConfigurationError(["BETTER_AUTH_SECRET"]);
      },
    );

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: "Authentication service unavailable" });
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("pragma")).toBe("no-cache");
  });
});
