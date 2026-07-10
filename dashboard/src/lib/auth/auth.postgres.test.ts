import { betterAuth } from "better-auth";
import { createLocalJWKSet, jwtVerify, type JSONWebKeySet } from "jose";
import { Client, Pool } from "pg";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  applyAuthSchemaMigrations,
  applyPreparedAuthMigration,
  loadAuthSchemaFiles,
  type MigrationClient,
} from "../../../scripts/apply-auth-schema";
import { prepareAuthMigration } from "../../../scripts/auth-schema";
import {
  AUTH_JWT_EXPIRATION,
  buildBetterAuthOptions,
  handleBetterAuthRequest,
  type BetterAuthSettings,
  type BetterAuthServer,
} from "../auth";
import type { AuthEmailMessage } from "./email";

const databaseURL = process.env.TEST_DATABASE_URL;
const ORIGIN = "https://dashboard.integration.test";
const AUTH_BASE = `${ORIGIN}/api/auth`;
const API_AUDIENCE = "https://api.integration.test";
const PASSWORD = "original-password-123";
const NEW_PASSWORD = "replacement-password-456";
const EXPECTED_TABLES = [
  "account",
  "jwks",
  "rateLimit",
  "session",
  "user",
  "verification",
];

if (!databaseURL) {
  describe.skip(
    "Better Auth disposable PostgreSQL integration (skipped without TEST_DATABASE_URL)",
    () => {
      it("requires TEST_DATABASE_URL pointing to disposable PostgreSQL", () => undefined);
    },
  );
} else {
  describe("Better Auth disposable PostgreSQL integration", () => {
    let migrationClient: Client;
    let authPool: Pool;
    let authServer: BetterAuthServer;
    let publicTablesBefore: string[];
    const emails: AuthEmailMessage[] = [];

    beforeAll(async () => {
      migrationClient = new Client({ connectionString: databaseURL });
      await migrationClient.connect();
      publicTablesBefore = await listTables(migrationClient, "public");
      await migrationClient.query('DROP SCHEMA IF EXISTS "auth" CASCADE');
      const files = await loadAuthSchemaFiles();
      const firstApply = await applyAuthSchemaMigrations(
        migrationClient as unknown as MigrationClient,
        files,
      );
      expect(firstApply).toEqual({ applied: 1, skipped: 0 });
      const secondApply = await applyAuthSchemaMigrations(
        migrationClient as unknown as MigrationClient,
        files,
      );
      expect(secondApply).toEqual({ applied: 0, skipped: 1 });

      authPool = new Pool({
        connectionString: databaseURL,
        options: "-c search_path=auth",
        max: 3,
        allowExitOnIdle: true,
      });
      const settings: BetterAuthSettings = {
        baseURL: ORIGIN,
        captchaAllowedHostnames: ["dashboard.integration.test"],
        databaseURL,
        jwtAudience: API_AUDIENCE,
        openSignupEnabled: true,
        secret: "integration-only-better-auth-secret-1234567890",
        secureCookies: true,
        smtp: {
          from: "auth@integration.test",
          host: "localhost",
          password: "unused",
          port: 587,
          secure: false,
          user: "unused",
        },
        trustedOrigins: [ORIGIN],
        // The production resolver always requires Turnstile. This disposable
        // integration omits only that network plugin so auth/database flows are
        // deterministic and do not call Cloudflare.
        turnstileSecretKey: undefined,
      };
      const actualAuth = betterAuth(
        buildBetterAuthOptions(settings, authPool, async (message) => {
          emails.push(message);
        }),
      );
      authServer = actualAuth;
    }, 30_000);

    afterAll(async () => {
      await authPool?.end().catch(() => undefined);
      if (migrationClient) {
        await migrationClient.query('DROP SCHEMA IF EXISTS "auth" CASCADE');
        await migrationClient.end().catch(() => undefined);
      }
    });

    it("places schema correctly and exercises roles, JWT/JWKS, verification, reset, and revocation", async () => {
      const authTables = await listTables(migrationClient, "auth");
      expect(authTables).toEqual(
        expect.arrayContaining([...EXPECTED_TABLES, "_better_auth_migrations"]),
      );
      for (const table of EXPECTED_TABLES) {
        expect(authTables).toContain(table);
        expect(publicTablesBefore).not.toContain(table);
      }
      expect(await listTables(migrationClient, "public")).toEqual(publicTablesBefore);

      const rollbackMigration = {
        name: "9999_rollback_probe.sql",
        sql: prepareAuthMigration(
          'create table "rollbackProbe" ("id" text);\ncreate table "user" ("id" text);',
        ),
      };
      await expect(
        applyPreparedAuthMigration(
          migrationClient as unknown as MigrationClient,
          rollbackMigration,
        ),
      ).rejects.toThrow();
      expect(
        await migrationClient.query("SELECT to_regclass('auth.\"rollbackProbe\"') AS table"),
      ).toMatchObject({ rows: [{ table: null }] });

      const hostileEmail = "hostile-role@integration.test";
      const hostileSignup = await authRequest("/sign-up/email", {
        method: "POST",
        body: {
          email: hostileEmail,
          name: "Hostile Role",
          password: PASSWORD,
          role: "owner",
        },
      });
      expect(hostileSignup.status).toBe(400);
      const hostileRows = await migrationClient.query(
        'SELECT "role" FROM "auth"."user" WHERE "email" = $1',
        [hostileEmail],
      );
      expect(hostileRows.rows).toHaveLength(0);

      const ownerEmail = "owner@integration.test";
      const signup = await authRequest("/sign-up/email", {
        method: "POST",
        body: { email: ownerEmail, name: "Owner", password: PASSWORD },
      });
      expect(signup.status).toBe(200);
      const ownerBeforeVerification = await userByEmail(ownerEmail);
      expect(ownerBeforeVerification).toMatchObject({
        role: "trader",
        emailVerified: false,
      });

      const verification = emails.find(
        ({ subject, to }) => subject.includes("Verify") && to === ownerEmail,
      );
      expect(verification).toBeDefined();
      const verifyResponse = await authRequest(verification!.text.split(": ").at(-1)!);
      expect([200, 302]).toContain(verifyResponse.status);
      const verifiedOwner = await userByEmail(ownerEmail);
      expect(verifiedOwner).toMatchObject({ emailVerified: true });
      expect(await sessionCount(ownerBeforeVerification.id)).toBe(0);
      const verifyReplay = await authRequest(verification!.text.split(": ").at(-1)!);
      expect([200, 302]).toContain(verifyReplay.status);
      expect(responseCookies(verifyReplay)).toBe("");
      expect((await userByEmail(ownerEmail)).updatedAt).toEqual(verifiedOwner.updatedAt);
      expect(await sessionCount(ownerBeforeVerification.id)).toBe(0);

      const ownerSignIn = await signIn(ownerEmail, PASSWORD);
      expect(ownerSignIn.response.status).toBe(200);
      await migrationClient.query(
        'UPDATE "auth"."user" SET "role" = $1 WHERE "id" = $2',
        ["owner", ownerBeforeVerification.id],
      );

      const adminEmail = "admin@integration.test";
      const createAdmin = await authRequest("/admin/create-user", {
        method: "POST",
        cookie: ownerSignIn.cookie,
        body: {
          email: adminEmail,
          name: "Admin",
          password: PASSWORD,
          role: "admin",
        },
      });
      expect(createAdmin.status).toBe(200);
      const admin = await userByEmail(adminEmail);
      expect(admin.role).toBe("admin");
      await migrationClient.query(
        'UPDATE "auth"."user" SET "emailVerified" = true WHERE "id" = $1',
        [admin.id],
      );
      const adminSignIn = await signIn(adminEmail, PASSWORD);
      expect(adminSignIn.response.status).toBe(200);

      const selfPromotion = await authRequest("/admin/set-role", {
        method: "POST",
        cookie: adminSignIn.cookie,
        body: { userId: admin.id, role: "owner" },
      });
      expect(selfPromotion.status).toBe(403);
      const modifyOwner = await authRequest("/admin/update-user", {
        method: "POST",
        cookie: adminSignIn.cookie,
        body: { userId: ownerBeforeVerification.id, data: { name: "Taken Over" } },
      });
      expect(modifyOwner.status).toBe(403);
      expect((await userByEmail(ownerEmail)).name).toBe("Owner");

      for (const hostileRole of [["owner", "admin"], "constructor", "owner,admin"]) {
        const response = await authRequest("/admin/set-role", {
          method: "POST",
          cookie: ownerSignIn.cookie,
          body: { userId: admin.id, role: hostileRole },
        });
        expect(response.status).toBe(400);
        expect((await userByEmail(adminEmail)).role).toBe("admin");
      }
      for (const role of ["viewer", "trader", "admin"] as const) {
        const transition = await authRequest("/admin/set-role", {
          method: "POST",
          cookie: ownerSignIn.cookie,
          body: { userId: admin.id, role },
        });
        expect(transition.status).toBe(200);
        expect((await userByEmail(adminEmail)).role).toBe(role);
      }

      const tokenResponse = await authRequest("/token", {
        cookie: ownerSignIn.cookie,
      });
      expect(tokenResponse.status).toBe(200);
      expect(tokenResponse.headers.get("cache-control")).toBe("private, no-store");
      expect(tokenResponse.headers.get("pragma")).toBe("no-cache");
      const { token } = (await tokenResponse.json()) as { token: string };
      const jwksResponse = await authRequest("/jwks");
      expect(jwksResponse.status).toBe(200);
      const jwks = (await jwksResponse.json()) as JSONWebKeySet;
      const { payload, protectedHeader } = await jwtVerify(
        token,
        createLocalJWKSet(jwks),
        {
          algorithms: ["RS256"],
          issuer: ORIGIN,
          audience: API_AUDIENCE,
        },
      );
      expect(protectedHeader.alg).toBe("RS256");
      expect(payload).toMatchObject({
        sub: ownerBeforeVerification.id,
        iss: ORIGIN,
        aud: API_AUDIENCE,
        email: ownerEmail,
        email_verified: true,
        role: "owner",
      });
      expect(payload.exp! - payload.iat!).toBe(300);
      expect(AUTH_JWT_EXPIRATION).toBe("5m");

      const resetRequest = await authRequest("/request-password-reset", {
        method: "POST",
        body: { email: ownerEmail, redirectTo: `${ORIGIN}/reset-password` },
      });
      expect(resetRequest.status).toBe(200);
      const resetEmail = emails.find(
        ({ subject, to }) => subject.includes("Reset") && to === ownerEmail,
      );
      expect(resetEmail).toBeDefined();
      const resetURL = new URL(resetEmail!.text.split(": ").at(-1)!);
      const resetToken = resetURL.pathname.split("/").at(-1)!;
      const reset = await authRequest("/reset-password", {
        method: "POST",
        body: { token: resetToken, newPassword: NEW_PASSWORD },
      });
      expect(reset.status).toBe(200);
      const replayReset = await authRequest("/reset-password", {
        method: "POST",
        body: { token: resetToken, newPassword: "another-password-789" },
      });
      expect(replayReset.status).toBe(400);
      expect((await authRequest("/token", { cookie: ownerSignIn.cookie })).status).toBe(
        401,
      );
      expect((await signIn(ownerEmail, PASSWORD)).response.status).toBeGreaterThanOrEqual(
        400,
      );
      const newSignIn = await signIn(ownerEmail, NEW_PASSWORD);
      expect(newSignIn.response.status).toBe(200);

      const revoke = await authRequest("/revoke-sessions", {
        method: "POST",
        cookie: newSignIn.cookie,
        body: {},
      });
      expect(revoke.status).toBe(200);
      expect((await authRequest("/token", { cookie: newSignIn.cookie })).status).toBe(401);
    }, 30_000);

    async function authRequest(
      pathOrURL: string,
      options: {
        method?: string;
        body?: Record<string, unknown>;
        cookie?: string;
      } = {},
    ) {
      const headers = new Headers({ Origin: ORIGIN });
      if (options.body) headers.set("Content-Type", "application/json");
      if (options.cookie) headers.set("Cookie", options.cookie);
      const request = new Request(
        pathOrURL.startsWith("http") ? pathOrURL : `${AUTH_BASE}${pathOrURL}`,
        {
          method: options.method ?? "GET",
          headers,
          body: options.body ? JSON.stringify(options.body) : undefined,
          redirect: "manual",
        },
      );
      return handleBetterAuthRequest(request, () => authServer);
    }

    async function signIn(email: string, password: string) {
      const response = await authRequest("/sign-in/email", {
        method: "POST",
        body: { email, password },
      });
      return { response, cookie: responseCookies(response) };
    }

    async function userByEmail(email: string) {
      const result = await migrationClient.query(
        'SELECT "id", "name", "role", "emailVerified", "updatedAt" FROM "auth"."user" WHERE "email" = $1',
        [email],
      );
      expect(result.rows).toHaveLength(1);
      return result.rows[0] as {
        id: string;
        name: string;
        role: string;
        emailVerified: boolean;
        updatedAt: Date;
      };
    }

    async function sessionCount(userId: string) {
      const result = await migrationClient.query(
        'SELECT count(*)::int AS count FROM "auth"."session" WHERE "userId" = $1',
        [userId],
      );
      return result.rows[0]?.count as number;
    }
  });
}

async function listTables(client: Client, schema: string) {
  const result = await client.query(
    `SELECT table_name
       FROM information_schema.tables
      WHERE table_schema = $1 AND table_type = 'BASE TABLE'
      ORDER BY table_name`,
    [schema],
  );
  return result.rows.map(({ table_name }) => table_name as string);
}

function responseCookies(response: Response) {
  const headers = response.headers as Headers & { getSetCookie?: () => string[] };
  const values = headers.getSetCookie?.() ?? [headers.get("set-cookie")].filter(Boolean);
  return values.map((value) => value!.split(";", 1)[0]).join("; ");
}
